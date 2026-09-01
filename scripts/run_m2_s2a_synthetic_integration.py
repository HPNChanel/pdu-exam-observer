"""Run the built-in M2-S2A simulated preflight in an owned temporary root."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdu_exam_observer.m1 import M1Backend  # noqa: E402
from pdu_exam_observer.m2_d1_contract import PrivacyDecision  # noqa: E402
from pdu_exam_observer.m2_persistence import M2PersistenceStore  # noqa: E402
from pdu_exam_observer.m2_synthetic_integration import (  # noqa: E402
    IntegrationStatus,
    M2SyntheticPreflightCore,
    SyntheticEnvironmentBindings,
    SyntheticPreflightRequest,
    canonical_json_bytes,
)
from pdu_exam_observer.m2_synthetic_preflight_fixture import (  # noqa: E402
    BUILTIN_RUN_ID,
    build_builtin_preflight_bundle,
)

_ENCODER_POLICY_PREIMAGE = b"M2-S2A-SIMULATED-ENCODER-NOT-INVOKED-V1"


class _Lease:
    def __init__(self) -> None:
        self._held = False

    def acquire(self) -> bool:
        if self._held:
            return False
        self._held = True
        return True

    def release(self) -> None:
        self._held = False


class _Privacy:
    def inspect(self, _observation: object) -> PrivacyDecision:
        return PrivacyDecision.CLEAR


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_digest() -> str:
    names = (
        "m2_synthetic.py",
        "m2_d1_contract.py",
        "m2_persistence.py",
        "m2_synthetic_integration.py",
        "m2_synthetic_preflight_fixture.py",
    )
    bindings = {
        name: _sha256_file(ROOT / "src" / "pdu_exam_observer" / name) for name in names
    }
    encoded = json.dumps(bindings, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _rejected() -> dict[str, object]:
    return {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "collection_authorized": False,
        "d1_go": False,
        "device_gate_decision": "UNVERIFIED",
        "evidence_kind": "SIMULATED",
        "integration_failure_code": "REQUEST_INVALID",
        "integration_status": "NOT_PERSISTED",
        "package_contains_integration": False,
        "schema_version": 1,
        "status": "M2_S2A_SYNTHETIC_PREFLIGHT_NOT_PERSISTED",
        "temp_root_removed": True,
    }


def _run() -> tuple[dict[str, object], int]:
    temporary_path: Path | None = None
    result: dict[str, object]
    store: M2PersistenceStore | None = None
    backend: M1Backend | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="pdu-m2-s2a-") as temporary:
            temporary_path = Path(temporary)
            backend = M1Backend(
                temporary_path,
                encryption_status="UNVERIFIED",
                acl_status="UNVERIFIED",
            )
            study = backend.create_study("m2-s2a", idempotency_key="study-m2-s2a")
            participant = backend.create_participant(
                str(study["study_id"]), idempotency_key="person-m2-s2a"
            )
            session = backend.create_research_session(
                str(study["study_id"]),
                str(participant["participant_id"]),
                idempotency_key="session-m2-s2a",
                retention_policy_reference="synthetic-smoke-policy",
            )
            backend.store.close()
            backend = None
            pose_digest = _sha256_file(
                ROOT
                / "src"
                / "pdu_exam_observer"
                / "assets"
                / "models"
                / "pose_landmarker_lite.task"
            )
            bundle = build_builtin_preflight_bundle(pose_digest)
            bindings = SyntheticEnvironmentBindings(
                application_revision_digest=_source_digest(),
                release_manifest_digest=_sha256_file(ROOT / "packaging" / "RELEASE_MANIFEST.json"),
                pose_engine_digest=pose_digest,
                encoder_policy_digest=hashlib.sha256(_ENCODER_POLICY_PREIMAGE).hexdigest(),
            )
            store = M2PersistenceStore(temporary_path)
            core = M2SyntheticPreflightCore(
                runner=bundle.runner,
                privacy_guard=_Privacy(),
                owner_lease=_Lease(),
                persistence_store=store,
                environment_bindings=bindings,
            )
            receipt = core.execute(
                SyntheticPreflightRequest(
                    session_id=str(session["session_id"]),
                    intent_id="intent-m2-s2a-preflight",
                    artifact_id="artifact-m2-s2a-preflight",
                    run_id=BUILTIN_RUN_ID,
                    fixtures=bundle.fixtures,
                )
            )
            result = receipt.as_dict()
            store.close()
            store = None
        removed = temporary_path is not None and not temporary_path.exists()
        result["temp_root_removed"] = removed
        success = (
            result.get("integration_status") == IntegrationStatus.PERSISTED.value
            and result.get("d1_outcome") == "BACKEND_CONTRACT_PASS"
            and removed
        )
        return result, 0 if success else 2
    except Exception:
        return {
            **_rejected(),
            "integration_failure_code": "UNEXPECTED_FAILURE",
            "temp_root_removed": temporary_path is None or not temporary_path.exists(),
        }, 2
    finally:
        if store is not None:
            store.close()
        if backend is not None:
            backend.store.close()


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    result, exit_code = (_rejected(), 2) if arguments else _run()
    sys.stdout.buffer.write(canonical_json_bytes(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

