from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from pdu_exam_observer import m2_synthetic
from pdu_exam_observer.m1 import M1Backend
from pdu_exam_observer.m2_d1_contract import (
    D1FailureCode,
    FrameDisposition,
    InputKind,
    PrivacyDecision,
    ValidationOutcome,
)
from pdu_exam_observer.m2_persistence import M2PersistenceStore
from pdu_exam_observer.m2_synthetic import (
    FixtureInput,
    ProcessingState,
    QualityState,
    TechnicalFailureCode,
    TechnicalInputKind,
    TechnicalObservation,
)
from pdu_exam_observer.m2_synthetic_integration import (
    IntegrationFailureCode,
    IntegrationStatus,
    M2SyntheticPreflightCore,
    SyntheticEnvironmentBindings,
    SyntheticPreflightRequest,
    map_technical_observation,
)
from pdu_exam_observer.m2_synthetic_preflight_fixture import (
    BUILTIN_RUN_ID,
    FRAME_COUNT,
    build_builtin_preflight_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
ENGINE_HASH = "c" * 64


class Lease:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.acquired = 0
        self.released = 0

    def acquire(self) -> bool:
        self.acquired += 1
        return self.available

    def release(self) -> None:
        self.released += 1


class Privacy:
    def __init__(self, decision: PrivacyDecision = PrivacyDecision.CLEAR) -> None:
        self.decision = decision

    def inspect(self, _observation: object) -> PrivacyDecision:
        return self.decision


def _bindings(
    failures: tuple[D1FailureCode, ...] = (),
    *,
    application_digest: str = "a" * 64,
) -> SyntheticEnvironmentBindings:
    return SyntheticEnvironmentBindings(
        application_revision_digest=application_digest,
        release_manifest_digest="b" * 64,
        pose_engine_digest=ENGINE_HASH,
        encoder_policy_digest="d" * 64,
        injected_failure_codes=failures,
    )


def _research(
    root: Path,
    *,
    code: str,
    withdraw: bool = False,
    fault_hook: object | None = None,
) -> tuple[str, M2PersistenceStore]:
    backend = M1Backend(root, encryption_status="UNVERIFIED", acl_status="UNVERIFIED")
    study = backend.create_study(code, idempotency_key=f"study-{code}")
    participant = backend.create_participant(
        str(study["study_id"]), idempotency_key=f"person-{code}"
    )
    session = backend.create_research_session(
        str(study["study_id"]),
        str(participant["participant_id"]),
        idempotency_key=f"session-{code}",
        retention_policy_reference="synthetic-test-policy",
    )
    session_id = str(session["session_id"])
    if withdraw:
        backend.withdraw(session_id, idempotency_key=f"withdraw-{code}")
    backend.store.close()
    kwargs = {} if fault_hook is None else {"fault_hook": fault_hook}
    return session_id, M2PersistenceStore(root, **kwargs)  # type: ignore[arg-type]


def _request(session_id: str, fixtures: tuple[FixtureInput, ...]) -> SyntheticPreflightRequest:
    return SyntheticPreflightRequest(
        session_id=session_id,
        intent_id="intent-m2-s2a-preflight",
        artifact_id="artifact-m2-s2a-preflight",
        run_id=BUILTIN_RUN_ID,
        fixtures=fixtures,
    )


def _core(
    store: M2PersistenceStore,
    *,
    privacy: Privacy | None = None,
    bindings: SyntheticEnvironmentBindings | None = None,
) -> tuple[M2SyntheticPreflightCore, tuple[FixtureInput, ...]]:
    bundle = build_builtin_preflight_bundle(ENGINE_HASH)
    return (
        M2SyntheticPreflightCore(
            runner=bundle.runner,
            privacy_guard=privacy or Privacy(),
            owner_lease=Lease(),
            persistence_store=store,
            environment_bindings=bindings or _bindings(),
        ),
        bundle.fixtures,
    )


def _technical_observation(
    *,
    kind: TechnicalInputKind,
    quality: QualityState = QualityState.VALID,
    failure: TechnicalFailureCode | None = None,
) -> TechnicalObservation:
    processed_failures = {None, TechnicalFailureCode.QUALITY_INSUFFICIENT}
    state = (
        ProcessingState.PROCESSED
        if failure in processed_failures
        else ProcessingState.FAILED
    )
    value = TechnicalObservation(
        schema_version=1,
        technical_input_kind=kind,
        fixture_id="fixture-one",
        fixture_version="v1",
        run_id="run-one",
        frame_seq=0,
        captured_monotonic_ns=1_000_000_000,
        processed_monotonic_ns=1_010_000_000 if state is ProcessingState.PROCESSED else None,
        pose_engine_task_hash=ENGINE_HASH,
        preprocessing_id="synthetic-rgba-identity-v1",
        landmark_topology_version="mediapipe-33-v1",
        landmarks=(),
        landmark_missing_mask=((True,) * 33, (True,) * 33),
        pose_count=0 if state is ProcessingState.PROCESSED else None,
        quality_state=quality,
        processing_state=state,
        failure_code=failure,
        latency_ms=10 if state is ProcessingState.PROCESSED else None,
        fixture_input_hash="1" * 64,
        golden_expected_output_digest="2" * 64,
        result_digest="",
    )
    return value.with_result_digest(value.recompute_result_digest())


def test_fixture_input_digest_preserves_existing_vector_and_builtin_shape() -> None:
    bundle = build_builtin_preflight_bundle(ENGINE_HASH)
    first = bundle.fixtures[0]
    assert FRAME_COUNT == 977
    assert len(bundle.fixtures) == FRAME_COUNT
    assert len({item.fixture_id for item in bundle.fixtures}) == FRAME_COUNT
    assert all(item.run_id == BUILTIN_RUN_ID for item in bundle.fixtures)
    assert m2_synthetic.fixture_input_digest(first) == m2_synthetic._input_hash(first)


def test_successful_preflight_persists_canonical_pass_receipt(tmp_path: Path) -> None:
    session_id, store = _research(tmp_path / "root", code="pass")
    core, fixtures = _core(store)
    receipt = core.execute(_request(session_id, fixtures))
    assert receipt.integration_status is IntegrationStatus.PERSISTED
    assert receipt.d1_outcome is ValidationOutcome.BACKEND_CONTRACT_PASS
    assert receipt.d1_failure_code is None
    assert receipt.integration_failure_code is None
    assert receipt.device_gate_decision.value == "UNVERIFIED"
    assert receipt.d1_go is False
    assert receipt.observation_count == FRAME_COUNT
    assert receipt.artifact_sha256 == store.manifest(receipt.artifact_id or "")["sha256"]
    assert receipt.result_digest == receipt.recompute_digest()
    store.close()


def test_adapter_maps_deterministic_ai_and_quality_failure_exhaustively() -> None:
    deterministic = map_technical_observation(
        _technical_observation(kind=TechnicalInputKind.DETERMINISTIC_FIXTURE)
    )
    ai = map_technical_observation(
        _technical_observation(kind=TechnicalInputKind.AI_RENDERED_FIXTURE)
    )
    quality = map_technical_observation(
        _technical_observation(
            kind=TechnicalInputKind.DETERMINISTIC_FIXTURE,
            quality=QualityState.INSUFFICIENT,
            failure=TechnicalFailureCode.QUALITY_INSUFFICIENT,
        )
    )
    assert deterministic.source_kind is InputKind.TEST_CHART
    assert ai.source_kind is InputKind.SYNTHETIC_VIDEO
    assert quality.disposition is FrameDisposition.PROCESSED
    assert quality.quality_insufficient is True
    assert quality.failure_code is None


def test_quality_no_go_is_persisted_with_exact_failure_metadata(tmp_path: Path) -> None:
    session_id, store = _research(tmp_path / "root", code="quality")
    core, fixtures = _core(
        store, bindings=_bindings((D1FailureCode.QUALITY_INSUFFICIENT,))
    )
    receipt = core.execute(_request(session_id, fixtures))
    assert receipt.integration_status is IntegrationStatus.PERSISTED
    assert receipt.d1_outcome is ValidationOutcome.NO_GO
    assert receipt.d1_failure_code is D1FailureCode.QUALITY_INSUFFICIENT
    manifest = store.manifest(receipt.artifact_id or "")
    assert manifest["technical_failure_code"] == "QUALITY_INSUFFICIENT"
    store.close()


def test_privacy_no_go_is_persisted_and_separated_from_artifact_validity(tmp_path: Path) -> None:
    session_id, store = _research(tmp_path / "root", code="privacy")
    core, fixtures = _core(store, privacy=Privacy(PrivacyDecision.UNSAFE))
    receipt = core.execute(_request(session_id, fixtures))
    manifest = store.manifest(receipt.artifact_id or "")
    assert receipt.integration_status is IntegrationStatus.PERSISTED
    assert receipt.d1_outcome is ValidationOutcome.NO_GO
    assert receipt.d1_failure_code is D1FailureCode.PRIVACY_STOP
    assert manifest["validity_state"] == "VALID"
    assert manifest["technical_failure_code"] == "PRIVACY_STOP"
    store.close()


def test_mixed_reserved_run_mismatch_and_tampered_observation_are_rejected(
    tmp_path: Path,
) -> None:
    mutations: list[tuple[str, tuple[FixtureInput, ...]]] = []
    bundle = build_builtin_preflight_bundle(ENGINE_HASH)
    mixed = replace(
        bundle.fixtures[1],
        technical_input_kind=TechnicalInputKind.AI_RENDERED_FIXTURE,
    )
    reserved = replace(
        bundle.fixtures[0],
        technical_input_kind=TechnicalInputKind.NO_HUMAN_DEVICE_SCENE,
    )
    mutations.append(("mixed", (bundle.fixtures[0], mixed)))
    mutations.append(("reserved", (reserved,)))
    mutations.append(("run", (replace(bundle.fixtures[0], run_id="another-run"),)))
    for code, fixtures in mutations:
        session_id, store = _research(tmp_path / code, code=code)
        core, _ = _core(store)
        receipt = core.execute(_request(session_id, fixtures))
        assert receipt.integration_status is IntegrationStatus.NOT_PERSISTED
        assert receipt.integration_failure_code is IntegrationFailureCode.REQUEST_INVALID
        assert receipt.artifact_id is None and receipt.artifact_sha256 is None
        store.close()

    class TamperedRunner:
        def process(self, fixture: FixtureInput) -> TechnicalObservation:
            original = bundle.runner.process(fixture)
            tampered = replace(
                original,
                golden_expected_output_digest="0" * 64,
                result_digest="",
            )
            return replace(
                tampered,
                result_digest=tampered.recompute_result_digest(),
            )

    session_id, store = _research(tmp_path / "tamper", code="tamper")
    core = M2SyntheticPreflightCore(
        runner=TamperedRunner(),  # type: ignore[arg-type]
        privacy_guard=Privacy(),
        owner_lease=Lease(),
        persistence_store=store,
        environment_bindings=_bindings(),
    )
    receipt = core.execute(_request(session_id, (bundle.fixtures[0],)))
    assert receipt.integration_status is IntegrationStatus.NOT_PERSISTED
    assert receipt.integration_failure_code is IntegrationFailureCode.RUNNER_REJECTED
    store.close()


def test_semantically_tampered_d1_receipt_is_not_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, store = _research(tmp_path / "root", code="semantic")
    core, fixtures = _core(store)
    monkeypatch.setattr(
        "pdu_exam_observer.m2_synthetic_integration.verify_receipt_semantics",
        lambda _receipt: False,
    )
    receipt = core.execute(_request(session_id, fixtures))
    assert receipt.integration_status is IntegrationStatus.NOT_PERSISTED
    assert receipt.integration_failure_code is IntegrationFailureCode.D1_RECEIPT_INVALID
    assert store.manifest_or_none("artifact-m2-s2a-preflight") is None
    store.close()


def test_exact_replay_is_idempotent_and_changed_payload_collision_fails(tmp_path: Path) -> None:
    session_id, store = _research(tmp_path / "root", code="replay")
    first_core, first_fixtures = _core(store)
    first = first_core.execute(_request(session_id, first_fixtures))
    replay_core, replay_fixtures = _core(store)
    replay = replay_core.execute(_request(session_id, replay_fixtures))
    assert replay.artifact_sha256 == first.artifact_sha256
    changed_core, changed_fixtures = _core(
        store, bindings=_bindings(application_digest="e" * 64)
    )
    changed = changed_core.execute(_request(session_id, changed_fixtures))
    assert changed.integration_status is IntegrationStatus.NOT_PERSISTED
    assert changed.integration_failure_code is IntegrationFailureCode.PERSISTENCE_FAILED
    assert changed.artifact_id is None and changed.artifact_sha256 is None
    store.close()


def test_persistence_fault_and_withdrawal_race_never_claim_artifact(tmp_path: Path) -> None:
    def fail_write(stage: str) -> None:
        if stage == "write":
            raise OSError("injected")

    session_id, store = _research(tmp_path / "fault", code="fault", fault_hook=fail_write)
    core, fixtures = _core(store)
    failed = core.execute(_request(session_id, fixtures))
    assert failed.integration_status is IntegrationStatus.NOT_PERSISTED
    assert failed.integration_failure_code is IntegrationFailureCode.PERSISTENCE_FAILED
    assert failed.artifact_id is None and failed.artifact_sha256 is None
    store.close()

    session_id, store = _research(tmp_path / "withdrawn", code="withdrawn", withdraw=True)
    core, fixtures = _core(store)
    withdrawn = core.execute(_request(session_id, fixtures))
    assert withdrawn.integration_status is IntegrationStatus.NOT_PERSISTED
    assert withdrawn.integration_failure_code is IntegrationFailureCode.PERSISTENCE_FAILED
    assert withdrawn.artifact_id is None and withdrawn.artifact_sha256 is None
    store.close()


def test_persisted_artifact_is_canonical_minimized_and_hash_bound(tmp_path: Path) -> None:
    root = tmp_path / "root"
    session_id, store = _research(root, code="artifact")
    core, fixtures = _core(store)
    receipt = core.execute(_request(session_id, fixtures))
    manifest = store.manifest(receipt.artifact_id or "")
    payload = (root / str(manifest["relative_path"])).read_bytes()
    document = json.loads(payload)
    expected_payload = (
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    assert payload == expected_payload
    assert hashlib.sha256(payload).hexdigest() == receipt.artifact_sha256
    assert document["artifact_kind"] == "M2_SYNTHETIC_PREFLIGHT_RECEIPT"
    assert len(document["observation_result_digests"]) == FRAME_COUNT
    forbidden = {"landmarks", "session_id", "participant_id", "local_path", "device_id", "username"}
    assert forbidden.isdisjoint(document)
    assert forbidden.isdisjoint(document["d1_receipt"])
    store.close()


def test_cli_is_no_argument_deterministic_sanitized_and_cleans_temp_root() -> None:
    command = [sys.executable, str(ROOT / "scripts" / "run_m2_s2a_synthetic_integration.py")]
    first = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    second = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert first.stderr == second.stderr == b""
    document = json.loads(first.stdout)
    assert document["d1_outcome"] == "BACKEND_CONTRACT_PASS"
    assert document["device_gate_decision"] == "UNVERIFIED"
    assert document["d1_go"] is False
    assert document["temp_root_removed"] is True
    assert document["package_contains_integration"] is False
    assert {"path", "session_id", "participant_id", "device_id"}.isdisjoint(document)
    rejected = subprocess.run([*command, "--path", "x"], cwd=ROOT, capture_output=True, check=False)
    assert rejected.returncode == 2
    assert rejected.stderr == b""
    assert json.loads(rejected.stdout)["integration_failure_code"] == "REQUEST_INVALID"


def test_integration_surface_has_no_camera_audio_api_or_arbitrary_path() -> None:
    paths = (
        ROOT / "src" / "pdu_exam_observer" / "m2_synthetic_integration.py",
        ROOT / "src" / "pdu_exam_observer" / "m2_synthetic_preflight_fixture.py",
        ROOT / "scripts" / "run_m2_s2a_synthetic_integration.py",
    )
    forbidden_imports = {"cv2", "mediapipe", "fastapi", "subprocess"}
    for path in paths:
        source = path.read_text(encoding="utf-8")
        imports = {
            alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        }
        assert imports.isdisjoint(forbidden_imports)
        assert "--path" not in source
        assert "D1_GO" not in source
