from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from pdu_exam_observer.m1 import M1Backend
from pdu_exam_observer.m2_d1_contract import (
    D1FailureCode,
    PrivacyDecision,
    ValidationOutcome,
)
from pdu_exam_observer.m2_persistence import M2PersistenceStore
from pdu_exam_observer.m2_synthetic_evidence import (
    MAX_EVIDENCE_BYTES,
    STATUS,
    SyntheticEvidenceFailureCode,
    build_synthetic_evidence_bundle,
    verify_synthetic_evidence_bytes,
)
from pdu_exam_observer.m2_synthetic_integration import (
    M2SyntheticNominalCore,
    M2SyntheticPreflightCore,
    SyntheticEnvironmentBindings,
    SyntheticNominalRequest,
    SyntheticPreflightRequest,
)
from pdu_exam_observer.m2_synthetic_nominal_fixture import (
    BUILTIN_RUN_ID as NOMINAL_RUN_ID,
)
from pdu_exam_observer.m2_synthetic_nominal_fixture import build_builtin_nominal_bundle
from pdu_exam_observer.m2_synthetic_preflight_fixture import (
    BUILTIN_RUN_ID as PREFLIGHT_RUN_ID,
)
from pdu_exam_observer.m2_synthetic_preflight_fixture import build_builtin_preflight_bundle
from pdu_exam_observer.m2_synthetic_review import (
    SyntheticReviewJobStatus,
    SyntheticReviewRunKind,
    SyntheticReviewRunRecord,
)

ENGINE_HASH = "c" * 64


class _Lease:
    def acquire(self) -> bool:
        return True

    def release(self) -> None:
        return None


class _Privacy:
    def inspect(self, _observation: object) -> PrivacyDecision:
        return PrivacyDecision.CLEAR


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _bindings(failures: tuple[D1FailureCode, ...] = ()) -> SyntheticEnvironmentBindings:
    return SyntheticEnvironmentBindings(
        application_revision_digest="a" * 64,
        release_manifest_digest="b" * 64,
        pose_engine_digest=ENGINE_HASH,
        encoder_policy_digest="d" * 64,
        injected_failure_codes=failures,
    )


def _research(root: Path, code: str) -> tuple[str, M2PersistenceStore]:
    backend = M1Backend(root, encryption_status="UNVERIFIED", acl_status="UNVERIFIED")
    study = backend.create_study(code, idempotency_key=f"study-{code}")
    participant = backend.create_participant(
        str(study["study_id"]), idempotency_key=f"participant-{code}"
    )
    session = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key=f"session-{code}",
        retention_policy_reference="synthetic-test-only",
    )
    backend.store.close()
    return str(session["session_id"]), M2PersistenceStore(root)


def _run(
    root: Path,
    *,
    nominal: bool = False,
    failures: tuple[D1FailureCode, ...] = (),
) -> tuple[dict[str, object], bytes]:
    session_id, store = _research(root, "nominal" if nominal else "preflight")
    bindings = _bindings(failures)
    if nominal:
        fixture = build_builtin_nominal_bundle(ENGINE_HASH)
        receipt = M2SyntheticNominalCore(
            runner=fixture.runner,
            privacy_guard=_Privacy(),
            owner_lease=_Lease(),
            persistence_store=store,
            environment_bindings=bindings,
        ).execute(
            SyntheticNominalRequest(
                session_id=session_id,
                intent_id="intent-evidence-nominal",
                artifact_id="artifact-evidence-nominal",
                run_id=NOMINAL_RUN_ID,
                fixtures=fixture.fixtures,
            )
        )
        kind = SyntheticReviewRunKind.NOMINAL_20M
    else:
        fixture = build_builtin_preflight_bundle(ENGINE_HASH)
        receipt = M2SyntheticPreflightCore(
            runner=fixture.runner,
            privacy_guard=_Privacy(),
            owner_lease=_Lease(),
            persistence_store=store,
            environment_bindings=bindings,
        ).execute(
            SyntheticPreflightRequest(
                session_id=session_id,
                intent_id="intent-evidence-preflight",
                artifact_id="artifact-evidence-preflight",
                run_id=PREFLIGHT_RUN_ID,
                fixtures=fixture.fixtures,
            )
        )
        kind = SyntheticReviewRunKind.PREFLIGHT_60S
    assert receipt.artifact_id is not None
    manifest = store.manifest(receipt.artifact_id)
    artifact = (root / str(manifest["relative_path"])).read_bytes()
    store.close()
    record = SyntheticReviewRunRecord(
        schema_version=1,
        request_id="synrun-0123456789abcdef0123456789abcdef",
        run_sequence=1,
        run_kind=kind,
        job_status=SyntheticReviewJobStatus.TERMINAL,
        service_failure_code=None,
        receipt=receipt,
    )
    return record.as_dict(), artifact


def _rehash(document: dict[str, object]) -> bytes:
    body = document["body"]
    document["body_sha256"] = hashlib.sha256(_canonical(body)[:-1]).hexdigest()
    return _canonical(document)


def test_preflight_bundle_is_canonical_deterministic_and_fully_verified(tmp_path: Path) -> None:
    record, artifact = _run(tmp_path / "root")
    first = build_synthetic_evidence_bundle(record, artifact)
    second = build_synthetic_evidence_bundle(record, artifact)
    verification = verify_synthetic_evidence_bytes(first.payload)
    assert first == second
    assert first.sha256 == hashlib.sha256(first.payload).hexdigest()
    assert first.filename == f"m2-s2d-{record['request_id']}.json"
    assert first.payload == _canonical(json.loads(first.payload))
    assert verification.result == "EVIDENCE_VERIFIED"
    assert verification.status == STATUS
    assert verification.failure_code is None
    assert verification.observation_count == 977


def test_nominal_bundle_contains_all_digests_and_stays_bounded(tmp_path: Path) -> None:
    record, artifact = _run(tmp_path / "root", nominal=True)
    exported = build_synthetic_evidence_bundle(record, artifact)
    document = json.loads(exported.payload)
    source = document["body"]["source_artifact"]
    assert len(source["observation_result_digests"]) == 18_077
    assert len(exported.payload) <= MAX_EVIDENCE_BYTES
    assert verify_synthetic_evidence_bytes(exported.payload).result == "EVIDENCE_VERIFIED"


def test_valid_persisted_no_go_remains_exportable(tmp_path: Path) -> None:
    record, artifact = _run(
        tmp_path / "root", failures=(D1FailureCode.QUALITY_INSUFFICIENT,)
    )
    assert record["receipt"]["d1_outcome"] == ValidationOutcome.NO_GO.value  # type: ignore[index]
    exported = build_synthetic_evidence_bundle(record, artifact)
    verified = verify_synthetic_evidence_bytes(exported.payload)
    assert verified.result == "EVIDENCE_VERIFIED"
    assert verified.failure_code is None


def test_reader_rejects_duplicate_noncanonical_oversized_and_open_envelopes(
    tmp_path: Path,
) -> None:
    record, artifact = _run(tmp_path / "root")
    valid = build_synthetic_evidence_bundle(record, artifact).payload
    document = json.loads(valid)
    open_envelope = {**document, "extra": True}
    duplicate = valid.replace(b'{"artifact_kind":', b'{"artifact_kind":"x","artifact_kind":', 1)
    pretty = json.dumps(document, indent=2).encode("utf-8")
    cases = (
        (duplicate, SyntheticEvidenceFailureCode.DUPLICATE_JSON_KEY),
        (pretty, SyntheticEvidenceFailureCode.NONCANONICAL_JSON),
        (b" " * (MAX_EVIDENCE_BYTES + 1), SyntheticEvidenceFailureCode.INPUT_TOO_LARGE),
        (_canonical(open_envelope), SyntheticEvidenceFailureCode.ENVELOPE_INVALID),
    )
    for payload, code in cases:
        receipt = verify_synthetic_evidence_bytes(payload)
        assert receipt.result == "EVIDENCE_REJECTED"
        assert receipt.failure_code is code


def test_nested_receipt_artifact_d1_and_observation_mutations_fail_closed(
    tmp_path: Path,
) -> None:
    record, artifact = _run(tmp_path / "root")
    document = json.loads(build_synthetic_evidence_bundle(record, artifact).payload)
    mutations = []
    for path, value in (
        (("source_run", "receipt", "result_digest"), "0" * 64),
        (("source_artifact_sha256",), "1" * 64),
        (("source_artifact", "d1_receipt", "result_digest"), "2" * 64),
        (("source_artifact", "observation_result_digests", 0), "3" * 64),
    ):
        mutated = json.loads(json.dumps(document))
        target = mutated["body"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        mutations.append(_rehash(mutated))
    for payload in mutations:
        assert verify_synthetic_evidence_bytes(payload).result == "EVIDENCE_REJECTED"


def test_authority_path_identity_and_raw_content_mutations_are_rejected(tmp_path: Path) -> None:
    record, artifact = _run(tmp_path / "root")
    document = json.loads(build_synthetic_evidence_bundle(record, artifact).payload)
    mutations = []
    for key, value in (
        ("research_ready", True),
        ("local_path", "C:/private/operator"),
        ("participant_id", "person-1"),
        ("raw_landmarks", [[0.1, 0.2]]),
    ):
        mutated = json.loads(json.dumps(document))
        mutated["body"]["authority_ceiling" if key == "research_ready" else "source_artifact"][
            key
        ] = value
        mutations.append(_rehash(mutated))
    for payload in mutations:
        assert verify_synthetic_evidence_bytes(payload).result == "EVIDENCE_REJECTED"


def test_cli_emits_one_sanitized_line_for_success_and_failure(tmp_path: Path) -> None:
    record, artifact = _run(tmp_path / "root")
    bundle = tmp_path / "bundle.json"
    bundle.write_bytes(build_synthetic_evidence_bundle(record, artifact).payload)
    command = [
        sys.executable,
        "scripts/verify_m2_s2d_synthetic_evidence.py",
        str(bundle),
    ]
    success = subprocess.run(command, check=False, capture_output=True, text=True)
    bundle.write_bytes(bundle.read_bytes().replace(b'"body_sha256":"', b'"body_sha256":"0', 1))
    failure = subprocess.run(command, check=False, capture_output=True, text=True)
    assert success.returncode == 0 and failure.returncode == 2
    assert success.stderr == failure.stderr == ""
    assert len(success.stdout.splitlines()) == len(failure.stdout.splitlines()) == 1
    assert json.loads(success.stdout)["result"] == "EVIDENCE_VERIFIED"
    assert json.loads(failure.stdout)["result"] == "EVIDENCE_REJECTED"
    assert str(tmp_path).lower() not in (success.stdout + failure.stdout).lower()


def test_bundle_reconstructs_exact_source_artifact_bytes_and_hash(tmp_path: Path) -> None:
    record, artifact = _run(tmp_path / "root")
    exported = build_synthetic_evidence_bundle(record, artifact)
    body = json.loads(exported.payload)["body"]
    reconstructed = _canonical(body["source_artifact"])
    assert reconstructed == artifact
    assert body["source_artifact_byte_size"] == len(artifact)
    assert body["source_artifact_sha256"] == hashlib.sha256(artifact).hexdigest()
