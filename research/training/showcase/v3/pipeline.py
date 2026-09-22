"""Executable five-fold training, calibration, ONNX export, and delivery.

Synthetic smoke mode proves plumbing only and exports a DEMO_ONLY model.
Research mode is separately gated by real, participant-disjoint exports and a
frozen protocol; neither mode performs participant collection.
"""

from __future__ import annotations

import copy
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pdu_exam_observer.showcase.preprocessing import PREPROCESSING_ID
from pdu_exam_observer.showcase.temporal_rules import RulePolicy, TemporalRuleEngine

from .calibration import (
    CONTEXT_ORDER,
    FUSION_FEATURE_ORDER,
    apply_fusion,
    apply_temperature,
    fit_logistic_fusion,
    fit_temperature,
    select_abstention_threshold,
)
from .export_bundle import export_model_bundle, export_reports_zip
from .splits import OuterFold, build_outer_folds
from .stgcn_mediapipe33 import CLASS_ORDER, build_stgcn_mediapipe33

SEED = 20260908


@dataclass(frozen=True, slots=True)
class Corpus:
    tensors: NDArray[np.float32]
    labels: NDArray[np.int64]
    context: NDArray[np.float32]
    participants: tuple[str, ...]
    source_kinds: tuple[str, ...]
    sample_ids: tuple[str, ...]
    dataset_manifest_sha256: str
    protocol_version: str
    sessions: tuple[str, ...] = ()
    phases: tuple[str, ...] = ()
    window_start_ms: tuple[int, ...] = ()
    window_end_ms: tuple[int, ...] = ()
    parent_provenance_ids: tuple[tuple[str, ...], ...] = ()
    source_record_ids: tuple[tuple[str, ...], ...] = ()
    session_duration_ms: dict[str, int] | None = None
    session_participants: dict[str, str] | None = None
    session_source_kinds: dict[str, str] | None = None
    session_phases: dict[str, str] | None = None
    record_provenance: dict[str, tuple[str, str, str]] | None = None
    raw_rule_frames: tuple[Any, ...] = ()
    reviewed_events: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class Delivery:
    model_zip: Path
    reports_zip: Path
    golden_inputs: Path
    golden_outputs: Path


@dataclass(frozen=True, slots=True)
class TrainedModel:
    model: Any
    camera_temperature: float
    fusion_temperature: float
    fusion_coefficients: NDArray[np.float64]
    fusion_intercepts: NDArray[np.float64]
    abstention_threshold: float
    trace: dict[str, Any]


def _seed_everything(seed: int) -> None:
    import torch

    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    try:
        torch.use_deterministic_algorithms(True)
    except RuntimeError:
        pass


def _synthetic_tensor(label: int, participant_index: int, sample_index: int) -> NDArray[np.float32]:
    rng = np.random.default_rng(SEED + label * 10_000 + participant_index * 100 + sample_index)
    tensor: NDArray[np.float32] = np.zeros((5, 90, 33), dtype=np.float32)
    tensor[3] = 0.9
    tensor[4] = 1.0
    tensor[:3] = rng.normal(0.0, 0.01, size=(3, 90, 33)).astype(np.float32)
    time = np.linspace(0.0, 1.0, 90, dtype=np.float32)
    if label == 0:
        tensor[0, :, 0] += np.sin(time * np.pi * 2) * 0.02
    elif label == 1:
        tensor[0, :, 15:23] += np.sin(time[:, None] * np.pi * 4) * 0.08
    elif label == 2:
        tensor[1, :, 0:11] += 0.45 + time[:, None] * 0.05
    else:
        tensor[0, :, 0:11] += 0.45 + time[:, None] * 0.05
    return tensor


def build_synthetic_corpus(*, samples_per_class_participant: int) -> Corpus:
    """Create deterministic pose-like tensors with explicit synthetic provenance."""

    if samples_per_class_participant < 1:
        raise ValueError("at least one sample per class/participant is required")
    tensors: list[NDArray[np.float32]] = []
    labels: list[int] = []
    contexts: list[list[float]] = []
    participants: list[str] = []
    sample_ids: list[str] = []
    for participant_index, participant in enumerate(f"P{i:02d}" for i in range(1, 13)):
        for label_index, label in enumerate(CLASS_ORDER):
            for sample_index in range(samples_per_class_participant):
                tensors.append(_synthetic_tensor(label_index, participant_index, sample_index))
                labels.append(label_index)
                contexts.append(
                    [
                        0.9,
                        0.1 + 0.02 * (participant_index % 3),
                        0.8,
                        0.0,
                        0.95 if label_index != 3 else 0.65,
                        0.0,
                    ]
                )
                participants.append(participant)
                sample_ids.append(f"synthetic-{participant}-{label.lower()}-{sample_index:03d}")
    generation = {
        "schema_version": 1,
        "mode": "SYNTHETIC_SMOKE",
        "seed": SEED,
        "samples_per_class_participant": samples_per_class_participant,
        "participant_count": 12,
        "class_order": list(CLASS_ORDER),
    }
    dataset_digest = hashlib.sha256(
        json.dumps(generation, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return Corpus(
        tensors=np.asarray(tensors, dtype=np.float32),
        labels=np.asarray(labels, dtype=np.int64),
        context=np.asarray(contexts, dtype=np.float32),
        participants=tuple(participants),
        source_kinds=("SYNTHETIC_SMOKE",) * len(tensors),
        sample_ids=tuple(sample_ids),
        dataset_manifest_sha256=dataset_digest,
        protocol_version="synthetic-smoke-not-protocol-data",
    )


def _indices(corpus: Corpus, participants: tuple[str, ...]) -> NDArray[np.int64]:
    selected = set(participants)
    return np.asarray(
        [index for index, participant in enumerate(corpus.participants) if participant in selected],
        dtype=np.int64,
    )


def _augment_training(
    tensors: NDArray[np.float32], labels: NDArray[np.int64], *, seed: int
) -> tuple[NDArray[np.float32], NDArray[np.int64]]:
    rng = np.random.default_rng(seed)
    children = tensors.copy()
    children[:, :3] += rng.normal(0.0, 0.003, size=children[:, :3].shape).astype(np.float32)
    children[:, :4] *= children[:, 4:5]
    return np.concatenate((tensors, children)), np.concatenate((labels, labels))


def _logits(model: Any, tensors: NDArray[np.float32]) -> NDArray[np.float64]:
    import torch

    model.eval()
    with torch.no_grad():
        return np.asarray(model(torch.from_numpy(tensors)).cpu().numpy(), dtype=np.float64)


def _fit_model(
    corpus: Corpus,
    *,
    train_participants: tuple[str, ...],
    calibration_participants: tuple[str, ...],
    forbidden_test_participants: tuple[str, ...],
    epochs: int,
    seed: int,
    smoke_architecture: bool,
) -> TrainedModel:
    import torch

    if set(train_participants) & set(calibration_participants):
        raise ValueError("train/calibration participants overlap")
    if (set(train_participants) | set(calibration_participants)) & set(forbidden_test_participants):
        raise ValueError("outer test participant entered fitting")
    train_indices = _indices(corpus, train_participants)
    calibration_indices = _indices(corpus, calibration_participants)
    if len(train_indices) == 0 or len(calibration_indices) == 0:
        raise ValueError("training and calibration partitions must be populated")
    train_tensors, train_labels = _augment_training(
        corpus.tensors[train_indices], corpus.labels[train_indices], seed=seed
    )
    calibration_tensors = corpus.tensors[calibration_indices]
    calibration_labels = corpus.labels[calibration_indices]
    _seed_everything(seed)
    widths = (4, 8, 8) if smoke_architecture else (32, 64, 64)
    model = build_stgcn_mediapipe33(widths=widths)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-4)
    loss_function = torch.nn.CrossEntropyLoss()
    train_x = torch.from_numpy(train_tensors)
    train_y = torch.from_numpy(train_labels)
    calibration_x = torch.from_numpy(calibration_tensors)
    calibration_y = torch.from_numpy(calibration_labels)
    best_state = copy.deepcopy(model.state_dict())
    best_loss = float("inf")
    best_epoch = 0
    patience = max(1, min(10, epochs))
    stale = 0
    history: list[dict[str, float | int]] = []
    for epoch in range(max(1, epochs)):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_loss = loss_function(model(train_x), train_y)
        train_loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            calibration_loss = loss_function(model(calibration_x), calibration_y)
        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": float(train_loss.item()),
                "calibration_loss": float(calibration_loss.item()),
            }
        )
        if float(calibration_loss.item()) < best_loss - 1e-8:
            best_loss = float(calibration_loss.item())
            best_epoch = epoch + 1
            best_state = copy.deepcopy(model.state_dict())
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    model.load_state_dict(best_state)
    camera_logits = _logits(model, calibration_tensors)
    camera_temperature = fit_temperature(camera_logits, calibration_labels)
    fusion = fit_logistic_fusion(
        camera_logits,
        corpus.context[calibration_indices],
        calibration_labels,
        seed=seed,
    )
    raw_fused_logits = (
        np.concatenate((camera_logits, corpus.context[calibration_indices]), axis=1)
        @ fusion.coefficients.T
        + fusion.intercepts
    )
    fusion_temperature = fit_temperature(raw_fused_logits, calibration_labels)
    fused_probabilities = apply_fusion(
        camera_logits,
        corpus.context[calibration_indices],
        fusion.coefficients,
        fusion.intercepts,
        temperature=fusion_temperature,
    )
    threshold = select_abstention_threshold(fused_probabilities, calibration_labels)
    return TrainedModel(
        model=model,
        camera_temperature=camera_temperature,
        fusion_temperature=fusion_temperature,
        fusion_coefficients=fusion.coefficients,
        fusion_intercepts=fusion.intercepts,
        abstention_threshold=threshold,
        trace={
            "selection_partition": "CALIBRATION_PARTICIPANT_DISJOINT",
            "early_stopping_participants": list(calibration_participants),
            "temperature_fit_participants": list(calibration_participants),
            "fusion_fit_participants": list(calibration_participants),
            "policy_fit_participants": list(calibration_participants),
            "forbidden_outer_test_participants": list(forbidden_test_participants),
            "best_epoch": best_epoch,
            "history": history,
            "train_real_or_synthetic_rows": int(len(train_indices)),
            "train_augmented_rows": int(len(train_indices)),
            "augmentation_parent_sample_ids": [corpus.sample_ids[index] for index in train_indices],
            "calibration_rows": int(len(calibration_indices)),
        },
    )


def _classification_metrics(
    logits: NDArray[np.float64], labels: NDArray[np.int64], temperature: float
) -> dict[str, object]:
    probabilities = apply_temperature(logits, temperature)
    predictions = probabilities.argmax(axis=1)
    return {
        "row_count": int(len(labels)),
        "accuracy": float((predictions == labels).mean()),
        "confusion_matrix": [
            [int(np.sum((labels == truth) & (predictions == predicted))) for predicted in range(4)]
            for truth in range(4)
        ],
        "claim_status": "SYNTHETIC_SMOKE_ONLY" if len(labels) else "UNAVAILABLE",
    }


def _run_outer_folds(corpus: Corpus, *, epochs: int, smoke_architecture: bool) -> dict[str, Any]:
    folds = build_outer_folds(
        tuple(f"P{i:02d}" for i in range(1, 13)), protocol_version=corpus.protocol_version
    )
    reports: list[dict[str, Any]] = []
    for fold in folds:
        trained = _fit_model(
            corpus,
            train_participants=fold.train,
            calibration_participants=fold.calibration,
            forbidden_test_participants=fold.test,
            epochs=epochs,
            seed=SEED + fold.index,
            smoke_architecture=smoke_architecture,
        )
        test_indices = _indices(corpus, fold.test)
        reports.append(
            {
                "fold_index": fold.index,
                "train_participants": list(fold.train),
                "calibration_participants": list(fold.calibration),
                "test_participants": list(fold.test),
                "participant_overlap": bool(
                    (set(fold.train) & set(fold.calibration))
                    or (set(fold.train) & set(fold.test))
                    or (set(fold.calibration) & set(fold.test))
                ),
                "pilot_included": bool(
                    {"P01", "P02"} & (set(fold.train) | set(fold.calibration) | set(fold.test))
                ),
                "fit_trace": trained.trace,
                "test_metrics": _classification_metrics(
                    _logits(trained.model, corpus.tensors[test_indices]),
                    corpus.labels[test_indices],
                    trained.camera_temperature,
                ),
                "event_metrics": {
                    "status": "UNAVAILABLE_SYNTHETIC_HAS_NO_CONTINUOUS_REAL_SESSION_TIMELINE"
                },
            }
        )
    return {
        "schema_version": 1,
        "split_policy_id": "five-outer-participant-disjoint-v1",
        "folds": reports,
        "pilot_exclusion": ["P01", "P02"],
        "test_selection_prohibited": True,
    }


def _export_onnx(model: Any, destination: Path) -> None:
    import torch

    destination.parent.mkdir(parents=True, exist_ok=True)
    model.eval()
    torch.onnx.export(
        model,
        (torch.zeros((1, 5, 90, 33), dtype=torch.float32),),
        str(destination),
        input_names=["pose_sequence"],
        output_names=["camera_logits"],
        dynamic_axes={"pose_sequence": {0: "batch"}, "camera_logits": {0: "batch"}},
        opset_version=18,
        dynamo=False,
    )


def _onnx_logits(model_path: Path, inputs: NDArray[np.float32]) -> NDArray[np.float32]:
    import onnxruntime as ort  # type: ignore[import-untyped]

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    return np.asarray(
        session.run(["camera_logits"], {"pose_sequence": inputs})[0], dtype=np.float32
    )


def run_synthetic_smoke(
    output_root: Path,
    *,
    epochs: int = 1,
    samples_per_class_participant: int = 1,
) -> Delivery:
    """Run all five fold seams and export an explicitly DEMO_ONLY final model."""

    corpus = build_synthetic_corpus(samples_per_class_participant=samples_per_class_participant)
    output_root.mkdir(parents=True, exist_ok=True)
    fold_report = _run_outer_folds(corpus, epochs=epochs, smoke_architecture=True)
    final_train = tuple(f"P{i:02d}" for i in range(3, 11))
    final_calibration = ("P11", "P12")
    trained = _fit_model(
        corpus,
        train_participants=final_train,
        calibration_participants=final_calibration,
        forbidden_test_participants=(),
        epochs=epochs,
        seed=SEED + 100,
        smoke_architecture=True,
    )
    model_path = output_root / "model.onnx"
    _export_onnx(trained.model, model_path)
    golden_inputs = corpus.tensors[_indices(corpus, ("P03",))][:2]
    torch_outputs = _logits(trained.model, golden_inputs).astype(np.float32)
    onnx_outputs = _onnx_logits(model_path, golden_inputs)
    np.testing.assert_allclose(onnx_outputs, torch_outputs, rtol=1e-4, atol=1e-5)
    model_version = f"pdu-stgcn-demo-{hashlib.sha256(model_path.read_bytes()).hexdigest()[:12]}"
    policy_version = "demo-policy-v1-not-protocol-frozen"
    manifest = {
        "schema_version": 1,
        "runtime_schema_min": 1,
        "runtime_schema_max": 1,
        "model_version": model_version,
        "policy_version": policy_version,
        "training_mode": "SYNTHETIC_SMOKE",
        "demo_only": True,
        "claim_status": "DEMO_ONLY_NOT_RESEARCH_PERFORMANCE",
        "model_purpose": "PIPELINE_AND_RUNTIME_SMOKE",
        "architecture": "ST_GCN_MEDIAPIPE33_SMOKE_WIDTH_4_8_8",
        "preprocessing_id": PREPROCESSING_ID,
        "topology": "mediapipe-33-v1",
        "fps": 15,
        "window_frames": 90,
        "stride_ms": 1_000,
        "input_name": "pose_sequence",
        "input_shape": [None, 5, 90, 33],
        "output_name": "camera_logits",
        "output_shape": [None, 4],
        "class_order": list(CLASS_ORDER),
        "context_order": list(CONTEXT_ORDER),
        "dataset_manifest_sha256": corpus.dataset_manifest_sha256,
        "split_policy_id": "five-outer-participant-disjoint-v1",
        "protocol_version": corpus.protocol_version,
        "training_source_counts": {
            "SYNTHETIC_SMOKE": len(corpus.tensors),
            "AUGMENTED": len(_indices(corpus, final_train)),
            "REAL": 0,
        },
        "runtime": {
            "package": "onnxruntime",
            "version": "1.29.0",
            "execution_provider": "CPUExecutionProvider",
        },
    }
    calibration = {
        "schema_version": 1,
        "fit_partition": "SYNTHETIC_SMOKE_CALIBRATION",
        "class_order": list(CLASS_ORDER),
        "feature_order": list(FUSION_FEATURE_ORDER),
        "camera_temperature": trained.camera_temperature,
        "fusion_temperature": trained.fusion_temperature,
        "fusion_coefficients": trained.fusion_coefficients.tolist(),
        "fusion_intercepts": trained.fusion_intercepts.tolist(),
        "fit_participants": list(final_calibration),
        "source_counts": {"SYNTHETIC_SMOKE": int(len(_indices(corpus, final_calibration)))},
    }
    policy = {
        "schema_version": 1,
        "policy_version": policy_version,
        "selection_partition": "SYNTHETIC_SMOKE_CALIBRATION",
        "abstention_threshold": trained.abstention_threshold,
        "minimum_coverage": 0.75,
        "minimum_pose_visibility": 0.55,
        "maximum_frame_gap_ratio": 0.20,
        "maximum_scaled_focus_signal_age": 1.0,
        "operator_outcome_on_abstention": "TECHNICAL_INSUFFICIENT",
        "primary_tiou": None,
        "event_policy": None,
        "protocol_freeze_status": "NOT_APPLICABLE_SYNTHETIC_SMOKE",
    }
    model_zip, golden_input_path, golden_output_path = export_model_bundle(
        output_root / "pdu-stgcn-demo-model.zip",
        model_path=model_path,
        manifest=manifest,
        calibration=calibration,
        policy=policy,
        golden_inputs=golden_inputs,
        golden_outputs=onnx_outputs,
        model_card=(
            "# PDU ST-GCN synthetic smoke model\n\n"
            "Status: DEMO_ONLY. This synthetic model verifies training, ONNX export, "
            "bundle import, and CPU inference. It is not research-performance evidence "
            "and is rejected for REAL sessions. Human review remains required.\n"
        ),
    )
    environment = {
        "schema_version": 1,
        "python": sys.version,
        "platform": platform.platform(),
        "seed": SEED,
        "mode": "SYNTHETIC_SMOKE",
        "claim_status": "LOCAL_TECHNICAL_SMOKE_ONLY",
    }
    reports_zip = export_reports_zip(
        output_root / "pdu-stgcn-demo-reports.zip",
        {
            "fold_metrics.json": fold_report,
            "experiment_card.json": {
                "schema_version": 1,
                "question": (
                    "Does the executable training/evaluation path preserve split boundaries?"
                ),
                "population": "synthetic pose-like fixtures only",
                "dataset_manifest_sha256": corpus.dataset_manifest_sha256,
                "split_protocol": "five participant-disjoint smoke folds; pilot IDs excluded",
                "seeds": [SEED + index for index in range(5)],
                "limitations": [
                    "No real participants",
                    "No camera evidence",
                    "No research-performance claim",
                    "No continuous-session event metric from synthetic windows",
                ],
                "reproduction_command": (
                    "python -m research.training.showcase.v3.cli "
                    "--mode SYNTHETIC_SMOKE --output OUTPUT"
                ),
                "human_review_required": True,
            },
            "environment.json": environment,
            "data_counts.json": {
                "source_kind": {"SYNTHETIC_SMOKE": len(corpus.tensors)},
                "supervised_rows": len(corpus.tensors),
                "uncertain_rows_excluded": 0,
                "pilot_rows_excluded": 8 * samples_per_class_participant,
            },
            "evaluation.json": {
                "status": "UNAVAILABLE_SYNTHETIC_SMOKE",
                "research_performance_verified": False,
                "continuous_session_hours": None,
                "configurations": ["rules", "camera_only", "context_plus_abstention"],
            },
            "CLAIM_BOUNDARY.md": (
                "# Claim boundary\n\nLOCAL_TECHNICAL_SMOKE_ONLY. No real collection, "
                "research training, research evaluation, performance, deployment, "
                "or release claim.\n"
            ),
        },
    )
    return Delivery(model_zip, reports_zip, golden_input_path, golden_output_path)


def _load_research_corpus(export_root: Path, protocol: dict[str, Any]) -> Corpus:
    from .dataset import load_runtime_export

    export_paths = (
        tuple(sorted(export_root.glob("*.zip"))) if export_root.is_dir() else (export_root,)
    )
    if not export_paths or any(not path.is_file() or path.is_symlink() for path in export_paths):
        raise ValueError("RESEARCH_EXPORT_REQUIRED: trusted runtime export ZIPs are required")
    loaded = tuple(load_runtime_export(path) for path in export_paths)
    tensors = np.concatenate([item.tensors for item in loaded])
    labels = np.concatenate([item.labels for item in loaded])
    context = np.concatenate([item.context for item in loaded])
    participants = tuple(value for item in loaded for value in item.participants)
    sessions = tuple(value for item in loaded for value in item.sessions)
    source_kinds = tuple(value for item in loaded for value in item.source_kinds)
    phases = tuple(value for item in loaded for value in item.phases)
    sample_ids = tuple(value for item in loaded for value in item.sample_ids)
    starts = tuple(value for item in loaded for value in item.window_start_ms)
    ends = tuple(value for item in loaded for value in item.window_end_ms)
    parent_ids = tuple(value for item in loaded for value in item.parent_provenance_ids)
    source_record_ids = tuple(value for item in loaded for value in item.source_record_ids)
    durations: dict[str, int] = {}
    session_participants: dict[str, str] = {}
    session_sources: dict[str, str] = {}
    session_phases: dict[str, str] = {}
    record_provenance: dict[str, tuple[str, str, str]] = {}
    raw_rule_frames: list[Any] = []
    events: list[dict[str, object]] = []
    for item in loaded:
        for session_id, duration in item.session_duration_ms.items():
            if session_id in durations:
                raise ValueError("session pseudonym appears in multiple exports")
            durations[session_id] = duration
            session_participants[session_id] = item.session_participants[session_id]
            session_sources[session_id] = item.session_source_kinds[session_id]
            session_phases[session_id] = item.session_phases[session_id]
        for sample_id, provenance in item.record_provenance.items():
            if sample_id in record_provenance:
                raise ValueError("raw record sample ID appears in multiple exports")
            record_provenance[sample_id] = provenance
        raw_rule_frames.extend(item.raw_rule_frames)
        events.extend(item.reviewed_events)
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("supervised window IDs are not unique")
    confirmatory = set(protocol["confirmatory_participants"])
    keep = np.asarray(
        [
            participant in confirmatory and phase == "CONFIRMATORY"
            for participant, phase in zip(participants, phases, strict=True)
        ],
        dtype=bool,
    )
    if not keep.any():
        raise ValueError("no confirmatory supervised windows remain after pilot exclusion")
    indices = np.flatnonzero(keep)
    selected_participants = tuple(participants[index] for index in indices)
    if set(selected_participants) != confirmatory:
        raise ValueError("all ten confirmatory participants are required")
    digest = hashlib.sha256(
        "".join(sorted(item.manifest_sha256 for item in loaded)).encode()
    ).hexdigest()
    selected_sessions = {
        session_id
        for session_id, participant in session_participants.items()
        if participant in confirmatory
        and session_sources[session_id] == "REAL"
        and session_phases[session_id] == "CONFIRMATORY"
    }
    return Corpus(
        tensors=tensors[indices],
        labels=labels[indices],
        context=context[indices],
        participants=selected_participants,
        source_kinds=tuple(source_kinds[index] for index in indices),
        sample_ids=tuple(sample_ids[index] for index in indices),
        dataset_manifest_sha256=digest,
        protocol_version=str(protocol["protocol_version"]),
        sessions=tuple(sessions[index] for index in indices),
        phases=tuple(phases[index] for index in indices),
        window_start_ms=tuple(starts[index] for index in indices),
        window_end_ms=tuple(ends[index] for index in indices),
        parent_provenance_ids=tuple(parent_ids[index] for index in indices),
        source_record_ids=tuple(source_record_ids[index] for index in indices),
        session_duration_ms={
            session_id: duration
            for session_id, duration in durations.items()
            if session_id in selected_sessions
        },
        session_participants={
            session_id: session_participants[session_id] for session_id in selected_sessions
        },
        session_source_kinds={
            session_id: session_sources[session_id] for session_id in selected_sessions
        },
        session_phases={session_id: session_phases[session_id] for session_id in selected_sessions},
        record_provenance=record_provenance,
        raw_rule_frames=tuple(
            frame for frame in raw_rule_frames if frame.session_id in selected_sessions
        ),
        reviewed_events=tuple(
            event for event in events if event["session_id"] in selected_sessions
        ),
    )


def _assert_research_fold_sources(corpus: Corpus, fold: OuterFold) -> None:
    for partition_name, people in (("calibration", fold.calibration), ("test", fold.test)):
        if not people:
            continue
        indices = _indices(corpus, people)
        if not len(indices):
            raise ValueError(f"{partition_name} partition is empty")
        if any(corpus.source_kinds[index] != "REAL" for index in indices):
            raise ValueError(f"{partition_name} must contain REAL source_kind only")
        if any(corpus.phases[index] != "CONFIRMATORY" for index in indices):
            raise ValueError(f"{partition_name} contains pilot or unknown phase")
    train_indices = _indices(corpus, fold.train)
    provenance = corpus.record_provenance or {}
    for index in train_indices:
        if corpus.source_kinds[index] == "AUGMENTED":
            parents = corpus.parent_provenance_ids[index]
            child_participant = corpus.participants[index]
            if not parents or len(parents) != len(corpus.source_record_ids[index]):
                raise ValueError("augmented child does not preserve frame parent grouping")
            for parent in parents:
                parent_provenance = provenance.get(parent)
                if (
                    parent_provenance is None
                    or parent_provenance
                    != (child_participant, "REAL", "CONFIRMATORY")
                    or parent_provenance[0] not in fold.train
                ):
                    raise ValueError(
                        "every augmented parent must resolve to REAL data in its training fold"
                    )


def _predicted_events(
    corpus: Corpus,
    indices: NDArray[np.int64],
    predicted_labels: NDArray[np.int64],
    *,
    merge_gap_ms: int,
) -> tuple[Any, ...]:
    from .evaluation import Event

    rows = sorted(
        (
            corpus.sessions[index],
            corpus.participants[index],
            int(predicted_labels[position]),
            corpus.window_start_ms[index],
            corpus.window_end_ms[index],
        )
        for position, index in enumerate(indices)
        if int(predicted_labels[position]) in {2, 3}
    )
    merged: list[Event] = []
    for session, participant, label_index, start, end in rows:
        label = CLASS_ORDER[label_index]
        if (
            merged
            and merged[-1].session_id == session
            and merged[-1].label == label
            and start <= merged[-1].end_ms + merge_gap_ms
        ):
            previous = merged.pop()
            merged.append(
                Event(session, participant, label, previous.start_ms, max(previous.end_ms, end))
            )
        else:
            merged.append(Event(session, participant, label, start, end))
    return tuple(merged)


def _rule_events_from_raw(
    corpus: Corpus, fold: OuterFold, protocol: dict[str, Any]
) -> tuple[Any, ...]:
    from .evaluation import Event

    policy = RulePolicy.from_protocol_freeze(protocol)
    test_people = set(fold.test)
    frames_by_session: dict[str, list[Any]] = {}
    for frame in corpus.raw_rule_frames:
        if frame.participant_id in test_people:
            frames_by_session.setdefault(frame.session_id, []).append(frame)
    output: dict[tuple[str, str], Event] = {}
    for session_id, frames in sorted(frames_by_session.items()):
        engine = TemporalRuleEngine(policy)
        ordered = sorted(frames, key=lambda frame: frame.timestamp_ms)
        emitted = []
        for frame in ordered:
            emitted.extend(
                engine.advance(
                    frame.timestamp_ms,
                    frame.pose_count,
                    frame.down_score,
                    frame.side_score,
                    quality_ok=frame.quality_ok,
                )
            )
        duration = (corpus.session_duration_ms or {}).get(session_id)
        if duration is not None:
            emitted.extend(engine.close(duration))
        for event in emitted:
            output[(session_id, event.logical_id)] = Event(
                session_id,
                ordered[0].participant_id,
                event.label,
                event.start_ms,
                event.end_ms,
                event.eligible_onset_ms,
            )
    return tuple(output[key] for key in sorted(output))


def _research_fold_evaluation(
    corpus: Corpus,
    fold: OuterFold,
    trained: TrainedModel,
    protocol: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, tuple[Any, ...]]]:
    from .evaluation import Event, Session, evaluate_configurations

    indices = _indices(corpus, fold.test)
    logits = _logits(trained.model, corpus.tensors[indices])
    camera_labels = apply_temperature(logits, trained.camera_temperature).argmax(axis=1)
    fused = apply_fusion(
        logits,
        corpus.context[indices],
        trained.fusion_coefficients,
        trained.fusion_intercepts,
        temperature=trained.fusion_temperature,
    )
    context_labels = fused.argmax(axis=1).astype(np.int64)
    context_labels[fused.max(axis=1) < trained.abstention_threshold] = -1
    policy = protocol["event_policy"]
    predictions = {
        "rules": _rule_events_from_raw(corpus, fold, protocol),
        "camera_only": _predicted_events(
            corpus,
            indices,
            camera_labels,
            merge_gap_ms=int(policy["merge_gap_ms"]),
        ),
        "context_plus_abstention": _predicted_events(
            corpus,
            indices,
            context_labels,
            merge_gap_ms=int(policy["merge_gap_ms"]),
        ),
    }
    test_people = set(fold.test)
    sessions = tuple(
        Session(session_id, participant, duration, "REAL")
        for session_id, duration in sorted((corpus.session_duration_ms or {}).items())
        for participant in [(corpus.session_participants or {})[session_id]]
        if participant in test_people
    )
    truth = tuple(
        Event(
            str(item["session_id"]),
            str(item["participant_id"]),
            str(item["label"]),
            int(str(item["start_ms"])),
            int(str(item["end_ms"])),
            int(str(item["start_ms"])) + int(policy["persistence_ms"]),
        )
        for item in corpus.reviewed_events
        if item["participant_id"] in test_people
    )
    report = evaluate_configurations(
        sessions,
        truth,
        predictions,
        seed=SEED + fold.index,
        primary_tiou=float(protocol["primary_tiou"]),
    )
    report["abstention"] = {
        "count": int(np.sum(context_labels < 0)),
        "rate": float(np.mean(context_labels < 0)),
    }
    return report, predictions


def run_research_training(
    export_root: Path,
    protocol_freeze: Path,
    output_root: Path,
    *,
    epochs: int = 100,
) -> Delivery:
    """Run real research mode only after a self-hashed protocol freeze and split gates."""

    from .protocol import validate_protocol_freeze

    protocol = validate_protocol_freeze(protocol_freeze)
    corpus = _load_research_corpus(export_root, protocol)
    folds = build_outer_folds(
        tuple(["P01", "P02", *(f"P{i:02d}" for i in range(3, 13))]),
        protocol_version=corpus.protocol_version,
    )
    fold_reports: list[dict[str, Any]] = []
    for fold in folds:
        _assert_research_fold_sources(corpus, fold)
        trained = _fit_model(
            corpus,
            train_participants=fold.train,
            calibration_participants=fold.calibration,
            forbidden_test_participants=fold.test,
            epochs=epochs,
            seed=SEED + fold.index,
            smoke_architecture=False,
        )
        evaluation, _ = _research_fold_evaluation(corpus, fold, trained, protocol)
        fold_reports.append(
            {
                "fold_index": fold.index,
                "train_participants": list(fold.train),
                "calibration_participants": list(fold.calibration),
                "test_participants": list(fold.test),
                "fit_trace": trained.trace,
                "evaluation": evaluation,
                "participant_overlap": False,
                "pilot_included": False,
            }
        )
    final_train = tuple(f"P{i:02d}" for i in range(3, 11))
    final_calibration = ("P11", "P12")
    final_fold = OuterFold(5, final_train, final_calibration, ())
    _assert_research_fold_sources(corpus, final_fold)
    final = _fit_model(
        corpus,
        train_participants=final_train,
        calibration_participants=final_calibration,
        forbidden_test_participants=(),
        epochs=epochs,
        seed=SEED + 100,
        smoke_architecture=False,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    model_path = output_root / "model.onnx"
    _export_onnx(final.model, model_path)
    golden_inputs = corpus.tensors[_indices(corpus, ("P03",))][:2]
    torch_outputs = _logits(final.model, golden_inputs).astype(np.float32)
    onnx_outputs = _onnx_logits(model_path, golden_inputs)
    np.testing.assert_allclose(onnx_outputs, torch_outputs, rtol=1e-4, atol=1e-5)
    model_version = f"pdu-stgcn-research-{hashlib.sha256(model_path.read_bytes()).hexdigest()[:12]}"
    policy_version = f"{protocol['protocol_version']}-policy"
    source_counts = {
        source: corpus.source_kinds.count(source) for source in ("REAL", "AI_RENDERED", "AUGMENTED")
    }
    manifest = {
        "schema_version": 1,
        "runtime_schema_min": 1,
        "runtime_schema_max": 1,
        "model_version": model_version,
        "policy_version": policy_version,
        "training_mode": "RESEARCH",
        "demo_only": False,
        "research_ready": True,
        "claim_status": "UNVERIFIED_RESEARCH_RESULT_PENDING_HUMAN_REVIEW",
        "model_purpose": "RESEARCH_PROTOTYPE_HUMAN_REVIEW_ONLY",
        "architecture": "ST_GCN_MEDIAPIPE33",
        "preprocessing_id": PREPROCESSING_ID,
        "topology": "mediapipe-33-v1",
        "fps": 15,
        "window_frames": 90,
        "stride_ms": int(protocol["event_policy"]["stride_ms"]),
        "input_name": "pose_sequence",
        "input_shape": [None, 5, 90, 33],
        "output_name": "camera_logits",
        "output_shape": [None, 4],
        "class_order": list(CLASS_ORDER),
        "context_order": list(CONTEXT_ORDER),
        "dataset_manifest_sha256": corpus.dataset_manifest_sha256,
        "protocol_freeze_sha256": protocol["protocol_freeze_sha256"],
        "split_policy_id": "five-outer-participant-disjoint-v1",
        "protocol_version": protocol["protocol_version"],
        "training_source_counts": source_counts
        | {"GENERATED_TRAIN_ONLY_AUGMENTED": int(len(_indices(corpus, final_train)))},
        "runtime": {
            "package": "onnxruntime",
            "version": "1.29.0",
            "execution_provider": "CPUExecutionProvider",
        },
    }
    calibration = {
        "schema_version": 1,
        "fit_partition": "CALIBRATION_PARTICIPANT_DISJOINT",
        "class_order": list(CLASS_ORDER),
        "feature_order": list(FUSION_FEATURE_ORDER),
        "camera_temperature": final.camera_temperature,
        "fusion_temperature": final.fusion_temperature,
        "fusion_coefficients": final.fusion_coefficients.tolist(),
        "fusion_intercepts": final.fusion_intercepts.tolist(),
        "fit_participants": list(final_calibration),
        "source_counts": {"REAL": int(len(_indices(corpus, final_calibration)))},
    }
    policy = {
        "schema_version": 1,
        "policy_version": policy_version,
        "selection_partition": "CALIBRATION_PARTICIPANT_DISJOINT",
        "abstention_threshold": final.abstention_threshold,
        "minimum_coverage": 0.75,
        "minimum_pose_visibility": 0.55,
        "maximum_frame_gap_ratio": 0.20,
        "maximum_scaled_focus_signal_age": 1.0,
        "operator_outcome_on_abstention": "TECHNICAL_INSUFFICIENT",
        "primary_tiou": protocol["primary_tiou"],
        "event_policy": protocol["event_policy"],
        "protocol_freeze_status": "FROZEN_BEFORE_OUTER_TEST",
    }
    model_zip, golden_input_path, golden_output_path = export_model_bundle(
        output_root / "pdu-stgcn-research-model.zip",
        model_path=model_path,
        manifest=manifest,
        calibration=calibration,
        policy=policy,
        golden_inputs=golden_inputs,
        golden_outputs=onnx_outputs,
        model_card=(
            "# PDU ST-GCN research prototype\n\n"
            "Observable pose events only. This bundle requires the bound frozen protocol, "
            "uses participant-disjoint evaluation, maps abstention to TECHNICAL_INSUFFICIENT, "
            "and supports human review only. It does not establish intent or misconduct.\n"
        ),
    )
    reports_zip = export_reports_zip(
        output_root / "pdu-stgcn-research-reports.zip",
        {
            "fold_metrics.json": {
                "schema_version": 1,
                "folds": fold_reports,
                "primary_tiou": protocol["primary_tiou"],
            },
            "experiment_card.json": {
                "schema_version": 1,
                "dataset_manifest_sha256": corpus.dataset_manifest_sha256,
                "protocol_freeze_sha256": protocol["protocol_freeze_sha256"],
                "split_protocol": "five participant-disjoint outer folds",
                "seeds": [SEED + index for index in range(5)],
                "augmentation": "train-only; each generated child bound to parent sample_id",
                "calibration": "real calibration participants only",
                "human_review_required": True,
                "reproduction_command": (
                    "python -m research.training.showcase.v3.cli --mode RESEARCH "
                    "--export EXPORT_DIR --protocol-freeze FREEZE.json --output OUTPUT"
                ),
            },
            "data_counts.json": {
                "source_kind": source_counts,
                "confirmatory_supervised_windows": len(corpus.tensors),
                "pilot_rows_in_metrics": 0,
            },
            "environment.json": {
                "schema_version": 1,
                "python": sys.version,
                "platform": platform.platform(),
                "seed": SEED,
                "mode": "RESEARCH",
            },
            "CLAIM_BOUNDARY.md": (
                "# Claim boundary\n\nResults remain UNVERIFIED until the report, source counts, "
                "protocol freeze, and human review are inspected. Alerts are review prompts only.\n"
            ),
        },
    )
    return Delivery(model_zip, reports_zip, golden_input_path, golden_output_path)
