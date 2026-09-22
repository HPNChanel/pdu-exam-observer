from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from pdu_exam_observer.showcase.export_contract import build_research_export
from research.training.showcase.v3.dataset import load_runtime_export
from research.training.showcase.v3.pipeline import _load_research_corpus


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _export_bytes(
    *,
    export_id: str = "export-1",
    session_id: str = "P03-S1",
    labels: tuple[str, ...] | None = None,
) -> bytes:
    pose = [{"x": 0.0, "y": 0.0, "z": 0.0, "visibility": 0.9} for _ in range(33)]
    pose[11].update(x=0.4, y=0.3)
    pose[12].update(x=0.6, y=0.3)
    pose[23].update(x=0.45, y=0.6)
    pose[24].update(x=0.55, y=0.6)
    selected_labels = labels or (*(("NORMAL",) * 90), "UNCERTAIN")
    records = []
    for index, label in enumerate(selected_labels):
        records.append(
            {
                "export_id": export_id,
                "manifest_sha256": "",
                "schema_version": 1,
                "record_count": len(selected_labels),
                "sample_id": f"{session_id}-sample-{index}",
                "participant_pseudonym": "P03",
                "session_pseudonym": session_id,
                "source_kind": "REAL",
                "parent_provenance_id": None,
                "pose": {
                    "topology": "mediapipe-33",
                    "pose_count": 1,
                    "landmarks": [pose],
                },
                "label": label,
                "quality": {
                    "state": "SUFFICIENT",
                    "blur": 0.1,
                    "exposure": 0.8,
                    "visibility_mean": 0.9,
                    "frame_gap_ratio": 0.0,
                },
                "focus": {
                    "state": "EXAM_FOCUSED",
                    "signal_age_ms": 0,
                    "contaminated_by_operator": False,
                },
                "timing": {
                    "captured_ns": index * 66_666_667,
                    "offset_ms": index * 67,
                    "phase": "CONFIRMATORY",
                },
            }
        )
    return build_research_export(tuple(records), export_id=export_id)[0]


def test_runtime_export_loader_builds_masked_window_and_retains_audit_counts() -> None:
    loaded = load_runtime_export(_export_bytes())

    assert loaded.tensors.shape == (1, 5, 90, 33)
    assert loaded.labels.tolist() == [0]
    assert loaded.participants == ("P03",)
    assert loaded.source_kinds == ("REAL",)
    assert loaded.audit_label_counts["UNCERTAIN"] == 1
    assert loaded.source_record_ids[0][0] == "P03-S1-sample-0"
    assert loaded.session_participants == {"P03-S1": "P03"}
    assert len(loaded.raw_rule_frames) == 91


def test_runtime_export_loader_rejects_missing_quality_context() -> None:
    payload = _export_bytes()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        records = [json.loads(line) for line in archive.read("records.jsonl").splitlines()]
    records[0]["focus"].pop("signal_age_ms")
    output = build_research_export(tuple(records), export_id="export-2")[0]

    try:
        load_runtime_export(output)
    except ValueError as error:
        assert "focus" in str(error)
    else:
        raise AssertionError("missing research focus context was accepted")


def test_all_uncertain_session_remains_in_continuous_denominator(tmp_path: Path) -> None:
    export_root = tmp_path / "exports"
    export_root.mkdir()
    (export_root / "learned.zip").write_bytes(_export_bytes())
    (export_root / "uncertain.zip").write_bytes(
        _export_bytes(
            export_id="export-uncertain",
            session_id="P03-S2",
            labels=("UNCERTAIN",) * 30,
        )
    )
    protocol = {
        "protocol_version": "test-v1",
        "confirmatory_participants": ["P03"],
    }

    corpus = _load_research_corpus(export_root, protocol)

    assert set(corpus.session_duration_ms or {}) == {"P03-S1", "P03-S2"}
    assert {frame.session_id for frame in corpus.raw_rule_frames} == {"P03-S1", "P03-S2"}
