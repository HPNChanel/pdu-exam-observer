from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

from pdu_exam_observer.m2_d1_n2_a0 import ApprovedRP2Triple
from pdu_exam_observer.m2_d1_n2_prepare import (
    CameraDeviceObservation,
    CameraEnumerationObservation,
    D1N2NoStreamAttestor,
    ExecutableObservation,
    FixedRP2Verifier,
    NoStreamAttestationStatus,
    RP2VerificationStatus,
    verify_fixed_rp2,
)
from pdu_exam_observer.m2_d1_n2_win32 import HandleInfo


def _builder() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "build_m2_d1_n2_rp2.py"
    spec = importlib.util.spec_from_file_location("d1_n2_rp2_builder_for_prepare", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rp2_root(tmp_path: Path) -> tuple[Path, ModuleType]:
    builder = _builder()
    repository = Path(__file__).resolve().parents[2]
    schema_relative = str(builder.SCHEMA_RELATIVE_PATH)
    candidate_relative = str(builder.CANDIDATE_RELATIVE_PATH)
    for relative in (schema_relative, candidate_relative, *builder.ARTIFACT_PATHS.values()):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repository / relative, target)
    assert builder.write_artifacts(
        tmp_path,
        tmp_path / schema_relative,
        tmp_path / candidate_relative,
    )
    return tmp_path, builder


def _approved(root: Path, builder: ModuleType) -> ApprovedRP2Triple:
    candidate_bytes = (root / builder.CANDIDATE_RELATIVE_PATH).read_bytes()
    candidate = json.loads(candidate_bytes)
    schema = json.loads((root / builder.SCHEMA_RELATIVE_PATH).read_bytes())
    schema_canonical = json.dumps(
        schema,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return ApprovedRP2Triple(
        static_bindings_digest=candidate["static_bindings_digest"],
        binding_schema_canonical_sha256=hashlib.sha256(schema_canonical).hexdigest(),
        candidate_exact_bytes_sha256=hashlib.sha256(candidate_bytes).hexdigest(),
        a0_approval_digest="a" * 64,
        approval_id_digest="b" * 64,
        issued_unix_ns=1,
        expires_unix_ns=900_000_000_001,
    )


class _LeaseOps:
    def __init__(self) -> None:
        self._next = 1
        self.paths: dict[int, Path] = {}
        self.identities: dict[Path, str] = {}
        self.reparse: set[Path] = set()
        self.fail_close = False
        self.opened: list[Path] = []
        self.closed: list[int] = []

    def open_inspection(self, path: str) -> int | None:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            return None
        handle = self._next
        self._next += 1
        self.paths[handle] = resolved
        self.opened.append(resolved)
        return handle

    def info(self, handle: int) -> HandleInfo:
        path = self.paths[handle]
        return HandleInfo(
            disk=True,
            reparse=path in self.reparse,
            directory=False,
            delete_pending=False,
            links=1,
            final_path=str(path),
            identity=self.identities.get(path, hashlib.sha256(str(path).encode()).hexdigest()),
            size=path.stat().st_size,
        )

    def seek_start(self, handle: int) -> bool:
        return handle in self.paths

    def read(self, handle: int, limit: int) -> bytes | None:
        return self.paths[handle].read_bytes()[:limit]

    def close(self, handle: int) -> bool:
        self.closed.append(handle)
        return not self.fail_close


def test_fixed_rp2_verifier_requires_independent_expected_triple_and_constructor_is_inert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "redirected")
    monkeypatch.setenv("LOCALAPPDATA", "redirected")
    assert list(inspect.signature(verify_fixed_rp2).parameters) == ["expected"]


def test_fixed_rp2_verifier_validates_exact_inventory_and_retains_leases(
    tmp_path: Path,
) -> None:
    root, builder = _rp2_root(tmp_path)
    ops = _LeaseOps()

    result = FixedRP2Verifier(root, ops).verify(_approved(root, builder))

    assert result.status is RP2VerificationStatus.VERIFIED
    assert result.lease_bundle is not None and result.lease_bundle.validate()
    assert result.static_bindings_digest == json.loads(
        (root / builder.CANDIDATE_RELATIVE_PATH).read_text(encoding="utf-8")
    )["static_bindings_digest"]
    assert len(ops.opened) == len(builder.ARTIFACT_PATHS) + 2
    assert result.lease_bundle.close()
    assert len(ops.closed) == len(ops.opened)


@pytest.mark.parametrize("mutation", ["artifact", "extra", "noncanonical"])
def test_fixed_rp2_verifier_rejects_content_and_schema_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    root, builder = _rp2_root(tmp_path)
    approved = _approved(root, builder)
    candidate = root / builder.CANDIDATE_RELATIVE_PATH
    if mutation == "artifact":
        (root / next(iter(builder.ARTIFACT_PATHS.values()))).write_bytes(b"drift")
    else:
        document = json.loads(candidate.read_text(encoding="utf-8"))
        if mutation == "extra":
            document["unexpected"] = True
        candidate.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    ops = _LeaseOps()
    result = FixedRP2Verifier(root, ops).verify(approved)

    assert result.status is RP2VerificationStatus.INVALID
    assert result.lease_bundle is None
    assert len(ops.closed) == len(ops.opened)


def test_fixed_rp2_verifier_rejects_reparse_alias_and_reports_cleanup_ambiguity(
    tmp_path: Path,
) -> None:
    root, builder = _rp2_root(tmp_path)
    approved = _approved(root, builder)
    artifact = (root / next(iter(builder.ARTIFACT_PATHS.values()))).resolve()
    ops = _LeaseOps()
    ops.reparse.add(artifact)
    assert (
        FixedRP2Verifier(root, ops).verify(approved).status
        is RP2VerificationStatus.INVALID
    )

    cleanup_ops = _LeaseOps()
    cleanup_ops.fail_close = True
    candidate = root / builder.CANDIDATE_RELATIVE_PATH
    candidate.write_bytes(b"invalid")
    assert (
        FixedRP2Verifier(root, cleanup_ops).verify(approved).status
        is RP2VerificationStatus.CLEANUP_FAILED
    )


def test_coordinated_rp2_regeneration_fails_against_prior_signed_triple(
    tmp_path: Path,
) -> None:
    root, builder = _rp2_root(tmp_path)
    prior = _approved(root, builder)
    bound_source = root / builder.ARTIFACT_PATHS["SRC_M2_D1_N2_CANONICAL_PY"]
    bound_source.write_bytes(bound_source.read_bytes() + b"\n# coordinated mutation\n")
    assert builder.write_artifacts(
        root,
        root / builder.SCHEMA_RELATIVE_PATH,
        root / builder.CANDIDATE_RELATIVE_PATH,
    )

    result = FixedRP2Verifier(root, _LeaseOps()).verify(prior)

    assert result.status is RP2VerificationStatus.INVALID


class _NativeLease:
    def __init__(self, *, close_ok: bool = True) -> None:
        self.valid = True
        self.close_ok = close_ok
        self.closed = False

    def validate(self) -> bool:
        return self.valid and not self.closed

    def close(self) -> bool:
        self.closed = True
        return self.close_ok


class _NativePreparation:
    def __init__(self, supervisor_sha256: str, supervisor_size_bytes: int) -> None:
        self.events: list[str] = []
        self.supervisor_lease = _NativeLease()
        self.camera_lease = _NativeLease()
        self.ffmpeg_lease = _NativeLease()
        self.cameras = (CameraDeviceObservation("Integrated Camera", True, True),)
        digest = "b" * 64
        self.supervisor = ExecutableObservation(
            digest,
            supervisor_sha256,
            supervisor_size_bytes,
            digest,
            None,
            self.supervisor_lease,
        )
        self.ffmpeg = ExecutableObservation(
            digest,
            digest,
            200,
            digest,
            digest,
            self.ffmpeg_lease,
        )

    def attest_supervisor(self) -> ExecutableObservation | None:
        self.events.append("supervisor")
        return self.supervisor

    def enumerate_camera_class(self) -> CameraEnumerationObservation:
        self.events.append("camera")
        return CameraEnumerationObservation(self.cameras, self.camera_lease)

    def attest_ffmpeg(self) -> ExecutableObservation | None:
        self.events.append("ffmpeg")
        return self.ffmpeg

    def dependency_observation_digest(self) -> str | None:
        self.events.append("dependency")
        return "c" * 64


def _native_for_root(root: Path, builder: ModuleType) -> _NativePreparation:
    candidate = json.loads(
        (root / builder.CANDIDATE_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    supervisor = candidate["environment_candidates"]["supervisor_executable_candidate"]
    return _NativePreparation(supervisor["sha256"], supervisor["size_bytes"])


def test_no_stream_attestor_builds_sanitized_typed_attestation_in_fixed_order(
    tmp_path: Path,
) -> None:
    root, builder = _rp2_root(tmp_path)
    ops = _LeaseOps()
    verifier = FixedRP2Verifier(root, ops)
    native = _native_for_root(root, builder)
    events: list[str] = []

    def verify_rp2(expected: ApprovedRP2Triple):  # type: ignore[no-untyped-def]
        events.append("rp2")
        return verifier.verify(expected)

    outcome = D1N2NoStreamAttestor(
        verify_rp2,
        native,
        entropy=lambda size: b"n" * size,
        unix_clock_ns=lambda: 5_000,
    ).attest(_approved(root, builder))

    assert outcome.status is NoStreamAttestationStatus.ATTESTED
    assert outcome.attestation is not None and outcome.attestation.valid()
    assert outcome.lease_bundle is not None and outcome.lease_bundle.validate()
    assert events + native.events == ["rp2", "supervisor", "camera", "ffmpeg", "dependency"]
    persisted = json.dumps(outcome.attestation.record_fields(), sort_keys=True)
    assert "Integrated Camera" not in persisted
    assert str(root) not in persisted
    assert "nnnn" not in persisted
    assert outcome.lease_bundle.close()


@pytest.mark.parametrize(
    "cameras",
    [
        (),
        (
            CameraDeviceObservation("one", True, True),
            CameraDeviceObservation("two", True, True),
        ),
        (CameraDeviceObservation("bad\nname", True, True),),
        (CameraDeviceObservation("camera", False, True),),
    ],
)
def test_no_stream_attestor_rejects_camera_mutants_and_closes_every_lease(
    tmp_path: Path,
    cameras: tuple[CameraDeviceObservation, ...],
) -> None:
    root, builder = _rp2_root(tmp_path)
    ops = _LeaseOps()
    native = _native_for_root(root, builder)
    native.cameras = cameras

    outcome = D1N2NoStreamAttestor(
        FixedRP2Verifier(root, ops).verify,
        native,
        entropy=lambda size: b"n" * size,
        unix_clock_ns=lambda: 5_000,
    ).attest(_approved(root, builder))

    assert outcome.status is NoStreamAttestationStatus.INVALID
    assert outcome.attestation is None and outcome.lease_bundle is None
    assert native.supervisor_lease.closed
    assert len(ops.closed) == len(ops.opened)


def test_no_stream_attestor_cleanup_ambiguity_is_nonlaunchable(tmp_path: Path) -> None:
    root, builder = _rp2_root(tmp_path)
    native = _native_for_root(root, builder)
    native.cameras = ()
    native.supervisor_lease.close_ok = False

    outcome = D1N2NoStreamAttestor(
        FixedRP2Verifier(root, _LeaseOps()).verify,
        native,
        entropy=lambda size: b"n" * size,
        unix_clock_ns=lambda: 5_000,
    ).attest(_approved(root, builder))

    assert outcome.status is NoStreamAttestationStatus.CLEANUP_FAILED
    assert outcome.attestation is None and outcome.lease_bundle is None


def test_no_stream_attestor_revalidates_exact_device_without_stream(tmp_path: Path) -> None:
    root, builder = _rp2_root(tmp_path)
    native = _native_for_root(root, builder)
    attestor = D1N2NoStreamAttestor(
        FixedRP2Verifier(root, _LeaseOps()).verify,
        native,
        entropy=lambda size: b"n" * size,
        unix_clock_ns=lambda: 5_000,
    )
    prepared = attestor.attest(_approved(root, builder))
    assert prepared.status is NoStreamAttestationStatus.ATTESTED

    native.camera_lease = _NativeLease()
    assert attestor.revalidate_device("Integrated Camera")
    assert native.camera_lease.closed
    native.camera_lease = _NativeLease()
    native.cameras = (CameraDeviceObservation("Different Camera", True, True),)
    assert not attestor.revalidate_device("Integrated Camera")
    assert native.camera_lease.closed
    assert prepared.lease_bundle is not None and prepared.lease_bundle.close()
