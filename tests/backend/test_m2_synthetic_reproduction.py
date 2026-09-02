from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest

from pdu_exam_observer.m2_persistence import PlatformUnsupported
from pdu_exam_observer.m2_synthetic_environment import (
    BOUND_SOURCE_RELATIVE_PATHS,
    current_synthetic_environment_bindings,
    synthetic_environment_binding_digest,
)
from pdu_exam_observer.m2_synthetic_evidence import (
    MAX_EVIDENCE_BYTES,
    SyntheticEvidenceError,
    SyntheticEvidenceFailureCode,
    canonical_json_bytes,
    load_verified_synthetic_evidence_bytes,
    verify_synthetic_evidence_bytes,
)
from pdu_exam_observer.m2_synthetic_reproduction import (
    ReproductionClassification,
    ReproductionFailureCode,
    TemporaryWorkspaceState,
    reproduce_synthetic_evidence_bytes,
    verify_reproduction_receipt_semantics,
)
from pdu_exam_observer.m2_synthetic_review import (
    SyntheticReviewJobStatus,
    SyntheticReviewRunKind,
    SyntheticReviewService,
)


@lru_cache(maxsize=2)
def _source_bundle(kind: SyntheticReviewRunKind) -> bytes:
    service = SyntheticReviewService.create_owned()
    try:
        queued = service.submit(
            kind,
            idempotency_key=f"m2-s2e-source-{kind.value.lower()}-0001",
        )
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            record = service.get(queued.request_id)
            if record.job_status is SyntheticReviewJobStatus.TERMINAL:
                return service.export_evidence(queued.request_id).payload
            time.sleep(0.005)
        raise AssertionError("synthetic source run did not terminate")
    finally:
        service.close()


def _rehash_body(document: dict[str, object]) -> bytes:
    body = document["body"]
    body_bytes = canonical_json_bytes(body)[:-1]
    document["body_sha256"] = hashlib.sha256(body_bytes).hexdigest()
    return canonical_json_bytes(document)


def test_structured_loader_preserves_the_existing_s2d_verification_contract() -> None:
    payload = _source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S)
    source = load_verified_synthetic_evidence_bytes(payload)
    verification = verify_synthetic_evidence_bytes(payload)
    assert verification.result == "EVIDENCE_VERIFIED"
    assert source.bundle_sha256 == hashlib.sha256(payload).hexdigest()
    assert source.observation_count == 977
    assert source.artifact_sha256 == hashlib.sha256(source.artifact_bytes).hexdigest()
    assert source.integration_receipt.result_digest == source.source_result_digest


def test_environment_binding_is_deterministic_and_uses_the_closed_source_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected_paths = (
        "src/pdu_exam_observer/m2_synthetic.py",
        "src/pdu_exam_observer/m2_d1_contract.py",
        "src/pdu_exam_observer/m2_persistence.py",
        "src/pdu_exam_observer/m2_synthetic_integration.py",
        "src/pdu_exam_observer/m2_synthetic_preflight_fixture.py",
        "src/pdu_exam_observer/m2_synthetic_nominal_fixture.py",
        "src/pdu_exam_observer/m2_synthetic_review.py",
        "src/pdu_exam_observer/m2_synthetic_evidence.py",
        "src/pdu_exam_observer/m2_synthetic_environment.py",
        "src/pdu_exam_observer/m2_synthetic_reproduction.py",
        "src/pdu_exam_observer/m2_packaged_reproduction.py",
        "src/pdu_exam_observer/__main__.py",
    )
    first = current_synthetic_environment_bindings()
    second = current_synthetic_environment_bindings()
    source = load_verified_synthetic_evidence_bytes(
        _source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S)
    )
    assert BOUND_SOURCE_RELATIVE_PATHS == expected_paths
    assert first == second
    assert first.injected_failure_codes == ()
    assert synthetic_environment_binding_digest(first) == source.environment_binding_digest

    import pdu_exam_observer.m2_synthetic_environment as environment

    repository = Path(__file__).parents[2]
    bundle_root = tmp_path / "PDU-Exam-Observer"
    internal_root = bundle_root / "_internal"
    binding_root = internal_root / "synthetic-bindings"
    packaged_binding_paths = (
        *expected_paths,
        "src/pdu_exam_observer/assets/models/pose_landmarker_lite.task",
    )
    for relative in packaged_binding_paths:
        target = binding_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repository / relative).read_bytes())
    packaged_manifest = b"packaged-release-manifest\n"
    (bundle_root / "RELEASE_MANIFEST.json").write_bytes(packaged_manifest)
    monkeypatch.setattr(environment.sys, "frozen", True, raising=False)
    monkeypatch.setattr(environment.sys, "_MEIPASS", str(internal_root), raising=False)
    monkeypatch.setattr(environment.sys, "executable", str(bundle_root / "PDUExamObserver.exe"))
    packaged = current_synthetic_environment_bindings()
    assert packaged.application_revision_digest == first.application_revision_digest
    assert packaged.pose_engine_digest == first.pose_engine_digest
    assert packaged.release_manifest_digest == hashlib.sha256(packaged_manifest).hexdigest()


def test_preflight_bundle_is_exactly_reproduced_after_workspace_cleanup() -> None:
    receipt = reproduce_synthetic_evidence_bytes(
        _source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S)
    )
    assert receipt.classification is ReproductionClassification.EXACTLY_REPRODUCED
    assert receipt.failure_code is None
    assert receipt.mismatch_fields == ()
    assert receipt.source_bundle_sha256 == receipt.reproduced_bundle_sha256
    assert receipt.source_observation_count == receipt.reproduced_observation_count == 977
    assert receipt.temporary_workspace_state is TemporaryWorkspaceState.REMOVED
    assert receipt.result_digest == receipt.recompute_digest()


def test_nominal_bundle_is_exactly_reproduced_with_all_nested_digests() -> None:
    receipt = reproduce_synthetic_evidence_bytes(
        _source_bundle(SyntheticReviewRunKind.NOMINAL_20M)
    )
    assert receipt.classification is ReproductionClassification.EXACTLY_REPRODUCED
    assert receipt.source_observation_count == receipt.reproduced_observation_count == 18_077
    assert receipt.source_observation_digest == receipt.reproduced_observation_digest
    assert receipt.source_d1_receipt_digest == receipt.reproduced_d1_receipt_digest
    assert receipt.source_artifact_sha256 == receipt.reproduced_artifact_sha256
    assert receipt.source_result_digest == receipt.reproduced_result_digest


def test_source_revision_mismatch_short_circuits_before_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pdu_exam_observer.m2_synthetic_reproduction as reproduction

    current = current_synthetic_environment_bindings()
    monkeypatch.setattr(
        reproduction,
        "current_synthetic_environment_bindings",
        lambda: replace(current, application_revision_digest="0" * 64),
    )

    def forbidden_replay(*_arguments: object) -> object:
        raise AssertionError("revision mismatch entered replay")

    monkeypatch.setattr(reproduction, "_replay_verified_source", forbidden_replay)
    receipt = reproduction.reproduce_synthetic_evidence_bytes(
        _source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S)
    )
    assert receipt.classification is ReproductionClassification.SOURCE_REVISION_MISMATCH
    assert receipt.failure_code is None
    assert receipt.mismatch_fields == ()
    assert receipt.temporary_workspace_state is TemporaryWorkspaceState.NOT_CREATED
    assert receipt.reproduced_bundle_sha256 is None


def test_semantic_mismatch_reports_only_sorted_closed_comparison_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pdu_exam_observer.m2_synthetic_reproduction as reproduction

    payload = _source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S)
    source = load_verified_synthetic_evidence_bytes(payload)
    changed = replace(
        source,
        bundle_sha256="f" * 64,
        observation_digest="e" * 64,
    )
    monkeypatch.setattr(
        reproduction,
        "_replay_verified_source",
        lambda *_arguments: (changed, TemporaryWorkspaceState.REMOVED),
    )
    receipt = reproduction.reproduce_synthetic_evidence_bytes(payload)
    assert receipt.classification is ReproductionClassification.SEMANTIC_RESULT_MISMATCH
    assert receipt.failure_code is None
    assert receipt.mismatch_fields == ("bundle_sha256", "observation_digest")
    assert set(receipt.mismatch_fields) <= reproduction.MISMATCH_FIELDS


def test_invalid_tampered_noncanonical_and_oversized_sources_never_create_replay() -> None:
    valid = _source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S)
    document = json.loads(valid)
    document["body"]["source_artifact"]["authority_ceiling"]["research_ready"] = True
    cases = (
        valid.replace(b'"body_sha256":"', b'"body_sha256":"0', 1),
        json.dumps(json.loads(valid), indent=2).encode("utf-8"),
        b" " * (MAX_EVIDENCE_BYTES + 1),
        _rehash_body(document),
    )
    for payload in cases:
        receipt = reproduce_synthetic_evidence_bytes(payload)
        assert receipt.classification is ReproductionClassification.REPRODUCTION_FAILED
        assert receipt.failure_code is ReproductionFailureCode.SOURCE_EVIDENCE_REJECTED
        assert receipt.temporary_workspace_state is TemporaryWorkspaceState.NOT_CREATED


def test_operational_replay_failures_do_not_publish_false_artifact_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pdu_exam_observer.m2_synthetic_reproduction as reproduction

    payload = _source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S)

    def unsupported(*_arguments: object) -> object:
        raise PlatformUnsupported("simulated platform failure")

    monkeypatch.setattr(reproduction, "_replay_verified_source", unsupported)
    unsupported_receipt = reproduction.reproduce_synthetic_evidence_bytes(payload)
    assert unsupported_receipt.failure_code is ReproductionFailureCode.PLATFORM_UNSUPPORTED
    assert unsupported_receipt.reproduced_artifact_sha256 is None

    def cleanup_failed(*_arguments: object) -> object:
        raise reproduction._ReproductionError(
            ReproductionFailureCode.TEMP_CLEANUP_FAILED,
            TemporaryWorkspaceState.CLEANUP_FAILED,
        )

    monkeypatch.setattr(reproduction, "_replay_verified_source", cleanup_failed)
    cleanup_receipt = reproduction.reproduce_synthetic_evidence_bytes(payload)
    assert cleanup_receipt.failure_code is ReproductionFailureCode.TEMP_CLEANUP_FAILED
    assert cleanup_receipt.temporary_workspace_state is TemporaryWorkspaceState.CLEANUP_FAILED
    assert cleanup_receipt.reproduced_bundle_sha256 is None

    def invalid_replay(*_arguments: object) -> object:
        raise SyntheticEvidenceError(SyntheticEvidenceFailureCode.ARTIFACT_HASH_MISMATCH)

    monkeypatch.setattr(reproduction, "_replay_verified_source", invalid_replay)
    invalid_receipt = reproduction.reproduce_synthetic_evidence_bytes(payload)
    assert invalid_receipt.failure_code is ReproductionFailureCode.REPLAY_EVIDENCE_INVALID
    assert invalid_receipt.reproduced_artifact_sha256 is None


def test_receipt_is_canonical_sanitized_and_rejects_forged_authority() -> None:
    import pdu_exam_observer.m2_synthetic_reproduction as reproduction

    receipt = reproduce_synthetic_evidence_bytes(
        _source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S)
    )
    encoded = canonical_json_bytes(receipt.as_dict())
    text = encoded.decode("utf-8").lower()
    assert verify_reproduction_receipt_semantics(receipt)
    assert encoded == canonical_json_bytes(json.loads(encoded))
    assert all(
        forbidden not in text
        for forbidden in ("local_path", "participant_id", "raw_landmarks", "username")
    )
    assert receipt.evidence_kind.value == "SIMULATED"
    assert receipt.device_gate_decision.value == "UNVERIFIED"
    assert not receipt.d1_go and not receipt.research_ready and not receipt.collection_authorized
    forged = replace(receipt, research_ready=True, result_digest="")
    forged = replace(forged, result_digest=forged.recompute_digest())
    assert not verify_reproduction_receipt_semantics(forged)
    forged_mismatch = replace(
        receipt,
        classification=ReproductionClassification.SEMANTIC_RESULT_MISMATCH,
        status=reproduction.NOT_VERIFIED_STATUS,
        mismatch_fields=("bundle_sha256",),
        result_digest="",
    )
    forged_mismatch = replace(
        forged_mismatch,
        result_digest=forged_mismatch.recompute_digest(),
    )
    assert not verify_reproduction_receipt_semantics(forged_mismatch)


def test_cli_is_deterministic_bounded_and_rejects_unsafe_input_surfaces(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle.json"
    bundle.write_bytes(_source_bundle(SyntheticReviewRunKind.PREFLIGHT_60S))
    command = [sys.executable, "scripts/reproduce_m2_s2e_synthetic_evidence.py", str(bundle)]
    first = subprocess.run(command, check=False, capture_output=True, text=True)
    second = subprocess.run(command, check=False, capture_output=True, text=True)
    extra = subprocess.run(command + ["extra"], check=False, capture_output=True, text=True)
    directory = subprocess.run(
        [sys.executable, command[1], str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout and first.stderr == second.stderr == ""
    assert len(first.stdout.splitlines()) == 1
    assert json.loads(first.stdout)["classification"] == "EXACTLY_REPRODUCED"
    assert extra.returncode == directory.returncode == 2
    assert extra.stderr == directory.stderr == ""
    combined = first.stdout + extra.stdout + directory.stdout
    assert str(tmp_path).lower() not in combined.lower()
    link = tmp_path / "bundle-link.json"
    try:
        link.symlink_to(bundle)
    except OSError:
        return
    linked = subprocess.run(
        [sys.executable, command[1], str(link)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert linked.returncode == 2 and linked.stderr == ""
