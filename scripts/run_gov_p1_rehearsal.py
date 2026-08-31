"""Run and verify the synthetic-only GOV-P1 withdrawal rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdu_exam_observer.domain.state import InvalidTransition  # noqa: E402
from pdu_exam_observer.m1 import M1Backend  # noqa: E402

DEFAULT_PACK_ROOT = ROOT / "research" / "pre_collection" / "gov_p1" / "v1"
DEFAULT_CONTRACT = DEFAULT_PACK_ROOT / "rehearsal-contract.v1.json"
DEFAULT_RECEIPT = DEFAULT_PACK_ROOT / "synthetic-ethics-data-receipt.v1.json"
DEFAULT_PROPOSAL = ROOT / "docs" / "source" / "DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx"
DEFAULT_GOV_P0_MANIFEST = (
    ROOT / "research" / "pre_collection" / "v1" / "pre-collection-pack.manifest.v1.json"
)
DEFAULT_M1_SOURCE = ROOT / "src" / "pdu_exam_observer" / "m1.py"
DEFAULT_RUNNER_SOURCE = Path(__file__).resolve()

CANONICAL_PROPOSAL_SHA256 = "2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5"
CANONICAL_GOV_P0_MANIFEST_SHA256 = (
    "c748548325c26fafcefa0543867e706ecb2064292fa591e6b4609de0e2402025"
)
REVIEWED_CONTRACT_SHA256 = (
    "e7b7b17e4cd977a5b95d7d576d69d696f251e51109aa9552b1f9e0bc82a61087"
)
RECEIPT_NAME = "synthetic-ethics-data-receipt.v1.json"
RECEIPT_STATUS = (
    "GOV_P1_SYNTHETIC_REHEARSAL_VERIFIED_"
    "PRODUCTION_RECONCILER_UNIMPLEMENTED"
)
BLOCKING_GATES = (
    "ACL_NOT_VERIFIED",
    "B0_3_CUSTODIAN_UNAVAILABLE",
    "B0_3_EXECUTION_AUTHORITY_NOT_ISSUED",
    "CONSENT_FORM_NOT_INSTITUTIONALLY_APPROVED",
    "ENCRYPTION_NOT_VERIFIED",
    "INSTITUTIONAL_APPROVAL_NOT_ISSUED",
    "LABELBOOK_NOT_FROZEN",
    "M2_DEVICE_EVIDENCE_UNVERIFIED",
    "M3_NOT_OPENED",
    "METHOD_THRESHOLDS_NOT_LOCKED",
    "PRODUCTION_RECONCILER_UNIMPLEMENTED",
    "PROTOCOL_NOT_FROZEN",
    "RESEARCH_COLLECTION_NOT_IMPLEMENTED",
    "RETENTION_DECISION_NOT_ISSUED",
    "STORAGE_ROOT_NOT_APPROVED",
)


class RehearsalError(ValueError):
    """A bounded, sanitized GOV-P1 rehearsal failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: object, *, trailing_newline: bool = True) -> bytes:
    """Return the single canonical JSON representation used by GOV-P1."""

    try:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise RehearsalError("CANONICALIZATION_FAILED") from exc
    return (text + ("\n" if trailing_newline else "")).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path, code: str) -> str:
    try:
        return _sha256(path.read_bytes())
    except OSError as exc:
        raise RehearsalError(code) from exc


def _strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RehearsalError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except RehearsalError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RehearsalError("INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise RehearsalError("ENVELOPE_INVALID")
    if canonical_json_bytes(value) != raw:
        raise RehearsalError("NONCANONICAL_JSON")
    return value


def _body_envelope(
    path: Path, *, artifact_kind: str, status: str
) -> tuple[dict[str, Any], str]:
    document = _strict_json(path)
    if set(document) != {
        "artifact_kind",
        "body",
        "body_sha256",
        "schema_version",
        "status",
    }:
        raise RehearsalError("ENVELOPE_INVALID")
    body = document.get("body")
    body_hash = document.get("body_sha256")
    if (
        document.get("artifact_kind") != artifact_kind
        or document.get("schema_version") != 1
        or document.get("status") != status
        or not isinstance(body, dict)
        or not isinstance(body_hash, str)
        or _sha256(canonical_json_bytes(body, trailing_newline=False)) != body_hash
    ):
        raise RehearsalError("BODY_HASH_MISMATCH")
    return body, body_hash


def parse_owned_relative_path(value: str) -> tuple[str, ...]:
    """Parse one fixed POSIX-style relative fixture path."""

    if not isinstance(value, str) or not value or "\\" in value:
        raise RehearsalError("OWNED_PATH_INVALID")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise RehearsalError("OWNED_PATH_INVALID")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    parts = posix.parts
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or value.startswith("//")
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise RehearsalError("OWNED_PATH_INVALID")
    return tuple(parts)


def _has_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RehearsalError("OWNED_PATH_INSPECTION_FAILED") from exc
    return path.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)


def _identity(path: Path) -> tuple[int, int, int, int, int, int]:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise RehearsalError("OWNED_PATH_INSPECTION_FAILED") from exc
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        getattr(metadata, "st_file_attributes", 0),
    )


def _checked_owned_file(
    root: Path,
    relative_path: str,
    *,
    reparse_probe: Callable[[Path], bool],
) -> Path:
    parts = parse_owned_relative_path(relative_path)
    if reparse_probe(root):
        raise RehearsalError("LINK_OR_REPARSE_DETECTED")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise RehearsalError("TEMP_ROOT_INVALID") from exc
    if reparse_probe(resolved_root):
        raise RehearsalError("LINK_OR_REPARSE_DETECTED")
    current = resolved_root
    for part in parts:
        current /= part
        if reparse_probe(current):
            raise RehearsalError("LINK_OR_REPARSE_DETECTED")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise RehearsalError("OWNED_PATH_INVALID") from exc
    if not resolved.is_file():
        raise RehearsalError("OWNED_TARGET_NOT_FILE")
    return resolved


def delete_owned_files(
    root: Path,
    fixtures: Sequence[dict[str, object]],
    *,
    reparse_probe: Callable[[Path], bool] = _has_link_or_reparse,
    before_unlink: Callable[[Path], None] | None = None,
) -> int:
    """Delete only validated manifest-owned synthetic fixture files."""

    checked: list[Path] = []
    for fixture in fixtures:
        relative_path = fixture.get("relative_path")
        expected_hash = fixture.get("payload_sha256")
        payload = fixture.get("payload_utf8")
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            raise RehearsalError("FIXTURE_CONTRACT_INVALID")
        if not isinstance(payload, str):
            raise RehearsalError("FIXTURE_CONTRACT_INVALID")
        target = _checked_owned_file(root, relative_path, reparse_probe=reparse_probe)
        try:
            actual = target.read_bytes()
        except OSError as exc:
            raise RehearsalError("FIXTURE_READ_FAILED") from exc
        if len(actual) != len(payload.encode("utf-8")):
            raise RehearsalError("FIXTURE_SIZE_MISMATCH")
        if _sha256(actual) != expected_hash:
            raise RehearsalError("FIXTURE_HASH_MISMATCH")
        checked_identity = _identity(target)
        if before_unlink is not None:
            before_unlink(target)
        rechecked = _checked_owned_file(
            root,
            relative_path,
            reparse_probe=reparse_probe,
        )
        if rechecked != target or _identity(rechecked) != checked_identity:
            raise RehearsalError("OWNED_IDENTITY_CHANGED")
        checked.append(target)
        try:
            target.unlink()
        except OSError as exc:
            raise RehearsalError("OWNED_DELETE_FAILED") from exc

    directories = sorted(
        {parent for target in checked for parent in target.parents if parent != root},
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass
    return len(checked)


def write_generated_file(
    root: Path,
    filename: str,
    payload: bytes,
    *,
    reparse_probe: Callable[[Path], bool] = _has_link_or_reparse,
) -> None:
    """Atomically replace one fixed generated leaf under a non-reparse root."""

    if (
        not isinstance(filename, str)
        or not filename
        or Path(filename).name != filename
        or filename in {".", ".."}
    ):
        raise RehearsalError("OUTPUT_PATH_INVALID")
    original_root = Path(root)
    if reparse_probe(original_root):
        raise RehearsalError("LINK_OR_REPARSE_DETECTED")
    try:
        resolved_root = original_root.resolve(strict=True)
    except OSError as exc:
        raise RehearsalError("OUTPUT_ROOT_INVALID") from exc
    if not resolved_root.is_dir():
        raise RehearsalError("OUTPUT_ROOT_INVALID")
    target = resolved_root / filename
    if target.exists() and reparse_probe(target):
        raise RehearsalError("LINK_OR_REPARSE_DETECTED")
    temporary = resolved_root / f".{filename}.{secrets.token_hex(8)}.tmp"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if reparse_probe(original_root):
            raise RehearsalError("LINK_OR_REPARSE_DETECTED")
        if original_root.resolve(strict=True) != resolved_root:
            raise RehearsalError("OUTPUT_ROOT_CHANGED")
        if target.exists() and reparse_probe(target):
            raise RehearsalError("LINK_OR_REPARSE_DETECTED")
        os.replace(temporary, target)
    except RehearsalError:
        raise
    except OSError as exc:
        raise RehearsalError("OUTPUT_WRITE_FAILED") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def load_contract(path: Path) -> tuple[dict[str, Any], str]:
    """Load and semantically validate the closed rehearsal contract."""

    if _file_sha256(path, "CONTRACT_UNAVAILABLE") != REVIEWED_CONTRACT_SHA256:
        raise RehearsalError("REVIEWED_SOURCE_HASH_MISMATCH")

    body, body_hash = _body_envelope(
        path,
        artifact_kind="GOV_P1_REHEARSAL_CONTRACT",
        status="SYNTHETIC_ONLY_APPROVED",
    )
    if set(body) != {
        "authority_ceiling",
        "expected",
        "fixtures",
        "immutable_inputs",
        "rehearsal",
    }:
        raise RehearsalError("CONTRACT_INVALID")
    authority = body.get("authority_ceiling")
    expected = body.get("expected")
    fixtures = body.get("fixtures")
    immutable = body.get("immutable_inputs")
    rehearsal = body.get("rehearsal")
    if (
        not isinstance(authority, dict)
        or not isinstance(expected, dict)
        or not isinstance(immutable, dict)
        or not isinstance(rehearsal, dict)
    ):
        raise RehearsalError("CONTRACT_INVALID")
    if not isinstance(fixtures, list) or len(fixtures) != 4:
        raise RehearsalError("CONTRACT_INVALID")
    if authority != {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "collection_authorized": False,
        "d1_go": False,
        "device_gate_decision": "UNVERIFIED",
        "participant_collection_authorized": False,
        "physical_camera_access_authorized": False,
        "research_ready": False,
    }:
        raise RehearsalError("AUTHORITY_CEILING_VIOLATION")
    if expected != {
        "artifact_count": 4,
        "collection_blocked_session_count": 2,
        "invalidated_artifact_count": 4,
        "owned_file_count": 4,
        "participant_count": 1,
        "pending_withdrawal_task_count": 4,
        "session_count": 2,
        "terminal_session_count": 2,
        "withdrawal_request_count": 2,
    }:
        raise RehearsalError("CONTRACT_INVALID")
    if immutable != {
        "gov_p0_manifest_sha256": CANONICAL_GOV_P0_MANIFEST_SHA256,
        "proposal_sha256": CANONICAL_PROPOSAL_SHA256,
    }:
        raise RehearsalError("IMMUTABLE_INPUT_MISMATCH")
    required_rehearsal = {
        "acl_status",
        "clock_epoch_seconds",
        "encryption_status",
        "export_capability_status",
        "production_reconciler_implemented",
        "retention_decision",
        "sentinel_payload_sha256",
        "sentinel_payload_utf8",
        "sentinel_relative_path",
        "study_code",
        "withdrawal_idempotency_keys",
    }
    if set(rehearsal) != required_rehearsal or rehearsal.get("acl_status") != "UNKNOWN":
        raise RehearsalError("CONTRACT_INVALID")
    if (
        rehearsal.get("encryption_status") != "UNKNOWN"
        or rehearsal.get("retention_decision") != "PENDING"
        or rehearsal.get("production_reconciler_implemented") is not False
        or rehearsal.get("export_capability_status")
        != "NOT_IMPLEMENTED_IN_M1_NOT_EXERCISED"
    ):
        raise RehearsalError("CONTRACT_INVALID")
    sentinel_path = rehearsal.get("sentinel_relative_path")
    sentinel_payload = rehearsal.get("sentinel_payload_utf8")
    sentinel_hash = rehearsal.get("sentinel_payload_sha256")
    if not isinstance(sentinel_path, str) or not isinstance(sentinel_payload, str):
        raise RehearsalError("CONTRACT_INVALID")
    parse_owned_relative_path(sentinel_path)
    if _sha256(sentinel_payload.encode("utf-8")) != sentinel_hash:
        raise RehearsalError("CONTRACT_INVALID")

    seen_ids: set[str] = set()
    seen_paths: set[str] = {sentinel_path}
    for fixture in fixtures:
        if not isinstance(fixture, dict) or set(fixture) != {
            "artifact_id",
            "parent_artifact_id",
            "payload_sha256",
            "payload_utf8",
            "relative_path",
            "session_slot",
        }:
            raise RehearsalError("FIXTURE_CONTRACT_INVALID")
        artifact_id = fixture.get("artifact_id")
        parent_id = fixture.get("parent_artifact_id")
        relative_path = fixture.get("relative_path")
        payload = fixture.get("payload_utf8")
        payload_hash = fixture.get("payload_sha256")
        if (
            not isinstance(artifact_id, str)
            or artifact_id in seen_ids
            or parent_id is not None
            and parent_id not in seen_ids
            or not isinstance(relative_path, str)
            or relative_path in seen_paths
            or not isinstance(payload, str)
            or _sha256(payload.encode("utf-8")) != payload_hash
            or fixture.get("session_slot") not in {"A", "B"}
        ):
            raise RehearsalError("FIXTURE_CONTRACT_INVALID")
        parse_owned_relative_path(relative_path)
        seen_ids.add(artifact_id)
        seen_paths.add(relative_path)
    expected_fixtures = (
        (
            "gov-p1-raw-a",
            None,
            "b4086ffcfac4f1fc397663231578ba69144fe3ef8e838646a9184621354475a3",
            "gov-p1-synthetic-raw-a-v1\n",
            "artifacts/session-a/raw-a.bin",
            "A",
        ),
        (
            "gov-p1-derived-a",
            "gov-p1-raw-a",
            "23eee65f685fcf1fd9a53bb663bcb60838e08ca9c76d3f483474ff7d00c24b53",
            '{"kind":"synthetic-derived","parent":"gov-p1-raw-a","schema_version":1}\n',
            "artifacts/session-a/derived-a.json",
            "A",
        ),
        (
            "gov-p1-raw-b",
            None,
            "11a6da872ffa764901b19e7246d13f24c21f6519807d3b7cf60d22806f2d6fc9",
            "gov-p1-synthetic-raw-b-v1\n",
            "artifacts/session-b/raw-b.bin",
            "B",
        ),
        (
            "gov-p1-derived-b",
            "gov-p1-raw-b",
            "423c1cf005c6ea2053317531416daca31f0c920deedc57b72429a223f77b9643",
            '{"kind":"synthetic-derived","parent":"gov-p1-raw-b","schema_version":1}\n',
            "artifacts/session-b/derived-b.json",
            "B",
        ),
    )
    observed_fixtures = tuple(
        (
            fixture["artifact_id"],
            fixture["parent_artifact_id"],
            fixture["payload_sha256"],
            fixture["payload_utf8"],
            fixture["relative_path"],
            fixture["session_slot"],
        )
        for fixture in fixtures
    )
    if observed_fixtures != expected_fixtures:
        raise RehearsalError("FIXTURE_CONTRACT_INVALID")
    return body, body_hash


def _verify_live_source_paths(m1_source: Path, runner_source: Path) -> None:
    try:
        m1_actual = Path(m1_source).resolve(strict=True)
        runner_actual = Path(runner_source).resolve(strict=True)
        m1_expected = DEFAULT_M1_SOURCE.resolve(strict=True)
        runner_expected = DEFAULT_RUNNER_SOURCE.resolve(strict=True)
    except OSError as exc:
        raise RehearsalError("LIVE_SOURCE_UNAVAILABLE") from exc
    if m1_actual != m1_expected or runner_actual != runner_expected:
        raise RehearsalError("LIVE_SOURCE_PATH_MISMATCH")


def _verify_immutable_inputs(proposal: Path, gov_p0_manifest: Path) -> None:
    if _file_sha256(proposal, "PROPOSAL_HASH_MISMATCH") != CANONICAL_PROPOSAL_SHA256:
        raise RehearsalError("PROPOSAL_HASH_MISMATCH")
    if (
        _file_sha256(gov_p0_manifest, "GOV_P0_HASH_MISMATCH")
        != CANONICAL_GOV_P0_MANIFEST_SHA256
    ):
        raise RehearsalError("GOV_P0_HASH_MISMATCH")


def _create_fixture(root: Path, fixture: dict[str, Any]) -> None:
    parts = parse_owned_relative_path(str(fixture["relative_path"]))
    current = root
    for part in parts[:-1]:
        current /= part
        try:
            current.mkdir(exist_ok=True)
        except OSError as exc:
            raise RehearsalError("FIXTURE_CREATE_FAILED") from exc
        if _has_link_or_reparse(current):
            raise RehearsalError("LINK_OR_REPARSE_DETECTED")
    target = current / parts[-1]
    try:
        with target.open("xb") as handle:
            handle.write(str(fixture["payload_utf8"]).encode("utf-8"))
    except OSError as exc:
        raise RehearsalError("FIXTURE_CREATE_FAILED") from exc


def _assert_late_mutations_blocked(backend: M1Backend, session_id: str) -> tuple[bool, bool]:
    try:
        backend.register_artifact("gov-p1-late-artifact", session_id)
    except InvalidTransition:
        artifact_blocked = True
    else:
        artifact_blocked = False
    try:
        backend.create_write_intent(session_id, "staging/partials/gov-p1-late.part")
    except InvalidTransition:
        write_blocked = True
    else:
        write_blocked = False
    if not artifact_blocked:
        raise RehearsalError("POST_WITHDRAWAL_ARTIFACT_ALLOWED")
    if not write_blocked:
        raise RehearsalError("POST_WITHDRAWAL_WRITE_ALLOWED")
    return artifact_blocked, write_blocked


def run_rehearsal(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    proposal: Path = DEFAULT_PROPOSAL,
    gov_p0_manifest: Path = DEFAULT_GOV_P0_MANIFEST,
    m1_source: Path = DEFAULT_M1_SOURCE,
    runner_source: Path = DEFAULT_RUNNER_SOURCE,
    temp_parent: Path | None = None,
    expected_receipt: Path | None = None,
) -> dict[str, object]:
    """Execute the isolated rehearsal and return its deterministic receipt."""

    contract, contract_body_hash = load_contract(contract_path)
    _verify_immutable_inputs(proposal, gov_p0_manifest)
    _verify_live_source_paths(m1_source, runner_source)
    m1_source_hash = _file_sha256(m1_source, "LIVE_SOURCE_UNAVAILABLE")
    runner_source_hash = _file_sha256(runner_source, "LIVE_SOURCE_UNAVAILABLE")
    rehearsal = contract["rehearsal"]
    fixtures = contract["fixtures"]
    if not isinstance(rehearsal, dict) or not isinstance(fixtures, list):
        raise RehearsalError("CONTRACT_INVALID")

    observations: dict[str, object] = {}
    temp_path: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="pdu-gov-p1-", dir=temp_parent) as temp_name:
            temp_path = Path(temp_name)
            backend: M1Backend | None = None
            try:
                backend = M1Backend(
                    temp_path,
                    encryption_status="UNKNOWN",
                    acl_status="UNKNOWN",
                    clock=lambda: float(rehearsal["clock_epoch_seconds"]),
                )
                for fixture in fixtures:
                    if not isinstance(fixture, dict):
                        raise RehearsalError("FIXTURE_CONTRACT_INVALID")
                    _create_fixture(temp_path, fixture)
                sentinel_path = temp_path.joinpath(
                    *parse_owned_relative_path(str(rehearsal["sentinel_relative_path"]))
                )
                with sentinel_path.open("xb") as handle:
                    handle.write(str(rehearsal["sentinel_payload_utf8"]).encode("utf-8"))

                study = backend.create_study(
                    str(rehearsal["study_code"]), idempotency_key="gov-p1-study"
                )
                participant = backend.create_participant(
                    str(study["study_id"]), idempotency_key="gov-p1-participant"
                )
                sessions = {
                    slot: backend.create_research_session(
                        str(study["study_id"]),
                        str(participant["participant_id"]),
                        idempotency_key=f"gov-p1-session-{slot.lower()}",
                    )
                    for slot in ("A", "B")
                }
                for fixture in fixtures:
                    slot = str(fixture["session_slot"])
                    parent = fixture["parent_artifact_id"]
                    parents = () if parent is None else (str(parent),)
                    backend.register_artifact(
                        str(fixture["artifact_id"]),
                        str(sessions[slot]["session_id"]),
                        parents=parents,
                    )

                keys = rehearsal["withdrawal_idempotency_keys"]
                if not isinstance(keys, list) or len(keys) != 2:
                    raise RehearsalError("CONTRACT_INVALID")
                first = backend.withdraw(
                    str(sessions["A"]["session_id"]), idempotency_key=str(keys[0])
                )
                second = backend.withdraw(
                    str(sessions["B"]["session_id"]), idempotency_key=str(keys[1])
                )
                first_id = first.get("withdrawal_receipt_id")
                if not isinstance(first_id, str) or not first_id or first != second:
                    raise RehearsalError("WITHDRAWAL_NOT_IDEMPOTENT")

                session_rows = [
                    backend.research_session(str(sessions[slot]["session_id"]))
                    for slot in ("A", "B")
                ]
                terminal_count = sum(row["state"] == "WITHDRAWN" for row in session_rows)
                blocked_count = sum(row["collection_blocked"] is True for row in session_rows)
                if terminal_count != 2:
                    raise RehearsalError("SESSION_NOT_TERMINAL")
                if blocked_count != 2:
                    raise RehearsalError("COLLECTION_NOT_BLOCKED")
                invalidated = sum(
                    backend.artifact_status(str(fixture["artifact_id"])) == "INVALIDATED"
                    for fixture in fixtures
                )
                if invalidated != 4:
                    raise RehearsalError("ARTIFACT_NOT_INVALIDATED")
                with backend.store._lock:
                    task_rows = backend.store.connection.execute(
                        "SELECT status FROM withdrawal_tasks ORDER BY artifact_id"
                    ).fetchall()
                pending_count = sum(str(row["status"]) == "PENDING" for row in task_rows)
                if len(task_rows) != 4 or pending_count != 4:
                    raise RehearsalError("TASK_COUNT_MISMATCH")
                artifact_blocked, write_blocked = _assert_late_mutations_blocked(
                    backend, str(sessions["B"]["session_id"])
                )
                recording_started = any(
                    backend.start_research_session(str(sessions[slot]["session_id"]))
                    for slot in ("A", "B")
                )
                if recording_started:
                    raise RehearsalError("RECORDING_STARTED")

                deleted = delete_owned_files(temp_path, fixtures)
                remaining = sum(
                    temp_path.joinpath(*parse_owned_relative_path(str(f["relative_path"]))).exists()
                    for f in fixtures
                )
                if remaining:
                    raise RehearsalError("OWNED_ARTIFACT_REMAINS")
                sentinel_bytes = sentinel_path.read_bytes()
                sentinel_preserved = (
                    _sha256(sentinel_bytes) == rehearsal["sentinel_payload_sha256"]
                )
                if not sentinel_preserved:
                    raise RehearsalError("SENTINEL_CHANGED")
                observations = {
                    "artifact_count": 4,
                    "canonical_withdrawal_receipt_nonempty": True,
                    "canonical_withdrawal_receipt_replayed": True,
                    "collection_blocked_session_count": blocked_count,
                    "invalidated_artifact_count": invalidated,
                    "late_artifact_registration_rejected": artifact_blocked,
                    "late_write_intent_rejected": write_blocked,
                    "out_of_manifest_sentinel_preserved": sentinel_preserved,
                    "owned_file_count_deleted": deleted,
                    "owned_file_count_remaining": remaining,
                    "participant_count": 1,
                    "pending_withdrawal_task_count": pending_count,
                    "recording_started": False,
                    "session_count": 2,
                    "terminal_session_count": terminal_count,
                    "withdrawal_request_count": 2,
                }
            except RehearsalError:
                raise
            except (InvalidTransition, KeyError, OSError, RuntimeError, ValueError) as exc:
                raise RehearsalError("M1_REHEARSAL_FAILED") from exc
            finally:
                if backend is not None:
                    backend.store.close()
    except RehearsalError:
        raise
    except OSError as exc:
        raise RehearsalError("TEMP_DISPOSAL_FAILED") from exc

    if temp_path is None or temp_path.exists():
        raise RehearsalError("TEMP_DISPOSAL_FAILED")
    body: dict[str, object] = {
        **observations,
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "blocking_gates": list(BLOCKING_GATES),
        "collection_authorized": False,
        "concurrent_same_account_mutation_resistant": False,
        "contract_body_sha256": contract_body_hash,
        "data_mode": "SYNTHETIC_ONLY",
        "device_gate_decision": "UNVERIFIED",
        "d1_go": False,
        "export_capability_status": "NOT_IMPLEMENTED_IN_M1_NOT_EXERCISED",
        "gov_p0_manifest_sha256": CANONICAL_GOV_P0_MANIFEST_SHA256,
        "human_review_required": True,
        "generated_output_atomic_replace": True,
        "m1_source_sha256": m1_source_hash,
        "participant_collection_authorized": False,
        "physical_camera_access_authorized": False,
        "production_reconciler_implemented": False,
        "proposal_sha256": CANONICAL_PROPOSAL_SHA256,
        "real_participant_count": 0,
        "real_person_data_present": False,
        "research_ready": False,
        "reviewed_source_hashes_pinned": True,
        "runner_sha256": runner_source_hash,
        "temporary_root_disposed": True,
        "path_identity_rechecked_before_unlink": True,
    }
    document: dict[str, object] = {
        "artifact_kind": "ETHICS_DATA_RECEIPT",
        "body": body,
        "body_sha256": _sha256(canonical_json_bytes(body, trailing_newline=False)),
        "schema_version": 1,
        "status": RECEIPT_STATUS,
    }
    if expected_receipt is not None:
        try:
            actual = expected_receipt.read_bytes()
        except OSError as exc:
            raise RehearsalError("RECEIPT_MISMATCH") from exc
        if actual != canonical_json_bytes(document):
            raise RehearsalError("RECEIPT_MISMATCH")
    return document


def write_receipt(
    pack_root: Path = DEFAULT_PACK_ROOT,
    *,
    contract_path: Path | None = None,
    proposal: Path = DEFAULT_PROPOSAL,
    gov_p0_manifest: Path = DEFAULT_GOV_P0_MANIFEST,
    m1_source: Path = DEFAULT_M1_SOURCE,
    runner_source: Path = DEFAULT_RUNNER_SOURCE,
    temp_parent: Path | None = None,
) -> dict[str, object]:
    """Run the rehearsal and write only its fixed generated receipt."""

    root = Path(pack_root)
    document = run_rehearsal(
        contract_path=contract_path or root / "rehearsal-contract.v1.json",
        proposal=proposal,
        gov_p0_manifest=gov_p0_manifest,
        m1_source=m1_source,
        runner_source=runner_source,
        temp_parent=temp_parent,
    )
    try:
        write_generated_file(root, RECEIPT_NAME, canonical_json_bytes(document))
    except RehearsalError as exc:
        if exc.code in {
            "LINK_OR_REPARSE_DETECTED",
            "OUTPUT_PATH_INVALID",
            "OUTPUT_ROOT_CHANGED",
            "OUTPUT_ROOT_INVALID",
        }:
            raise
        raise RehearsalError("RECEIPT_WRITE_FAILED") from exc
    return document


def _success_result(document: dict[str, object]) -> dict[str, object]:
    return {
        "collection_authorized": False,
        "failure_code": None,
        "receipt_body_sha256": document["body_sha256"],
        "research_ready": False,
        "result": "REHEARSAL_VERIFIED",
        "schema_version": 1,
    }


def _failure_result(code: str) -> dict[str, object]:
    return {
        "collection_authorized": False,
        "failure_code": code,
        "receipt_body_sha256": None,
        "research_ready": False,
        "result": "REHEARSAL_REJECTED",
        "schema_version": 1,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--proposal", type=Path, default=DEFAULT_PROPOSAL)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.write:
            document = write_receipt(proposal=arguments.proposal)
        else:
            document = run_rehearsal(
                proposal=arguments.proposal,
                expected_receipt=DEFAULT_RECEIPT,
            )
    except RehearsalError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(_failure_result(exc.code)))
        return 2
    except Exception:
        sys.stdout.buffer.write(canonical_json_bytes(_failure_result("UNEXPECTED_FAILURE")))
        return 2
    sys.stdout.buffer.write(canonical_json_bytes(_success_result(document)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
