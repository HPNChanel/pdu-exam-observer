"""Windows retained-handle deletion and durable reconciliation execution."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sqlite3
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from secrets import token_urlsafe
from typing import Protocol, cast

from pdu_exam_observer.configuration import ConfigurationError, validate_storage_root
from pdu_exam_observer.m1 import SchemaIntegrityError
from pdu_exam_observer.m1_r1 import ResearchStoreV3, _root_identity_digest
from pdu_exam_observer.reconciliation import (
    ConsumedChallenge,
    ReconciliationBlocked,
    ReconciliationPlan,
    ReconciliationPlanner,
    ReconciliationReceipt,
)


class DeletionBlocked(RuntimeError):
    def __init__(self, code: str, *, disposition_may_have_occurred: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.disposition_may_have_occurred = disposition_may_have_occurred


class DeletionPlatformUnsupported(DeletionBlocked):
    pass


class ReconciliationAuthorityNotIssued(PermissionError):
    pass


class ExecutionAuthority(Protocol):
    def permits_execution(
        self,
        *,
        root_identity_digest: str,
        execution_id: str,
        plan_sha256: str,
        target_ids: tuple[str, ...],
    ) -> bool: ...


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", ctypes.c_uint32),
        ("ftCreationTimeLow", ctypes.c_uint32),
        ("ftCreationTimeHigh", ctypes.c_uint32),
        ("ftLastAccessTimeLow", ctypes.c_uint32),
        ("ftLastAccessTimeHigh", ctypes.c_uint32),
        ("ftLastWriteTimeLow", ctypes.c_uint32),
        ("ftLastWriteTimeHigh", ctypes.c_uint32),
        ("dwVolumeSerialNumber", ctypes.c_uint32),
        ("nFileSizeHigh", ctypes.c_uint32),
        ("nFileSizeLow", ctypes.c_uint32),
        ("nNumberOfLinks", ctypes.c_uint32),
        ("nFileIndexHigh", ctypes.c_uint32),
        ("nFileIndexLow", ctypes.c_uint32),
    ]


class _FileDispositionInfo(ctypes.Structure):
    _fields_ = [("DeleteFile", ctypes.c_ubyte)]


@dataclass(frozen=True)
class LocalDeletionTarget:
    target_id: str
    root_scope: str
    relative_path: str
    expected_byte_size: int
    expected_sha256: str
    required_volume_identity_digest: str | None = None
    required_file_identity_digest: str | None = None


@dataclass(frozen=True)
class PredeleteSnapshot:
    byte_size: int
    sha256: str
    volume_identity_digest: str
    file_identity_digest: str


@dataclass(frozen=True)
class DeletionOutcome:
    target_id: str
    absence_verified: bool


@dataclass(frozen=True)
class ExecutionAuthorityBinding:
    root_identity_digest: str
    execution_id: str
    plan_sha256: str
    target_ids: tuple[str, ...]


class WindowsHandleDeletionPrimitive:
    """Delete one exact server-derived NTFS leaf while parent/target handles stay held."""

    def __init__(
        self,
        root: Path,
        *,
        before_absence_check: Callable[[Path], None] | None = None,
    ) -> None:
        if os.name != "nt":
            raise DeletionPlatformUnsupported("PLATFORM_UNSUPPORTED")
        try:
            self.root = validate_storage_root(root, create=False)
        except ConfigurationError as exc:
            raise DeletionBlocked("STORAGE_ROOT_INVALID") from exc
        self._kernel32 = ctypes.windll.kernel32
        self._before_absence_check = before_absence_check
        self._require_ntfs()

    def _require_ntfs(self) -> None:
        volume_path = ctypes.create_unicode_buffer(32768)
        if not self._kernel32.GetVolumePathNameW(
            str(self.root), volume_path, len(volume_path)
        ):
            raise DeletionPlatformUnsupported("FILESYSTEM_IDENTITY_UNAVAILABLE")
        filesystem = ctypes.create_unicode_buffer(256)
        if not self._kernel32.GetVolumeInformationW(
            volume_path.value,
            None,
            0,
            None,
            None,
            None,
            filesystem,
            len(filesystem),
        ):
            raise DeletionPlatformUnsupported("FILESYSTEM_IDENTITY_UNAVAILABLE")
        if filesystem.value.upper() != "NTFS":
            raise DeletionPlatformUnsupported("FILESYSTEM_NOT_NTFS")

    @staticmethod
    def _relative_parts(value: str) -> tuple[str, ...]:
        if not value or value.startswith(("/", "\\")) or "\\" in value or ":" in value:
            raise DeletionBlocked("TARGET_RELATIVE_PATH_INVALID")
        parts = PurePosixPath(value).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise DeletionBlocked("TARGET_RELATIVE_PATH_INVALID")
        if any(part.endswith((" ", ".")) for part in parts):
            raise DeletionBlocked("TARGET_RELATIVE_PATH_INVALID")
        return parts

    def _open(
        self,
        path: Path,
        *,
        directory: bool,
        desired_access: int,
        share: int,
    ) -> int:
        attributes = self._kernel32.GetFileAttributesW(str(path))
        if attributes == 0xFFFFFFFF or attributes & 0x400:
            raise DeletionBlocked("TARGET_REPARSE_OR_UNAVAILABLE")
        create_file = self._kernel32.CreateFileW
        create_file.restype = ctypes.c_void_p
        flags = 0x00200000 | (0x02000000 if directory else 0)
        handle = create_file(str(path), desired_access, share, None, 3, flags, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise DeletionBlocked("TARGET_HANDLE_ACQUISITION_FAILED")
        result = cast(int, handle)
        info = self._information(result)
        if info.dwFileAttributes & 0x400:
            self._kernel32.CloseHandle(result)
            raise DeletionBlocked("TARGET_REPARSE_OR_UNAVAILABLE")
        is_directory = bool(info.dwFileAttributes & 0x10)
        if is_directory != directory:
            self._kernel32.CloseHandle(result)
            raise DeletionBlocked("TARGET_FILESYSTEM_TYPE_INVALID")
        return result

    def _information(self, handle: int) -> _ByHandleFileInformation:
        information = _ByHandleFileInformation()
        if not self._kernel32.GetFileInformationByHandle(
            handle, ctypes.byref(information)
        ):
            raise DeletionBlocked("TARGET_IDENTITY_UNAVAILABLE")
        return information

    def _final_path(self, handle: int) -> Path:
        buffer = ctypes.create_unicode_buffer(32768)
        size = self._kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if size == 0 or size >= len(buffer):
            raise DeletionBlocked("TARGET_FINAL_PATH_UNAVAILABLE")
        return Path(buffer.value.removeprefix("\\\\?\\"))

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(
            os.path.normpath(str(right))
        )

    def _hash_handle(self, handle: int) -> tuple[int, str]:
        position = ctypes.c_longlong(0)
        if not self._kernel32.SetFilePointerEx(handle, 0, ctypes.byref(position), 0):
            raise DeletionBlocked("TARGET_READ_FAILED")
        digest = hashlib.sha256()
        total = 0
        buffer = ctypes.create_string_buffer(65536)
        while True:
            read = ctypes.c_uint32(0)
            if not self._kernel32.ReadFile(
                handle, buffer, len(buffer), ctypes.byref(read), None
            ):
                raise DeletionBlocked("TARGET_READ_FAILED")
            if read.value == 0:
                break
            digest.update(buffer.raw[: read.value])
            total += int(read.value)
        return total, digest.hexdigest()

    @staticmethod
    def _identity_snapshot(
        information: _ByHandleFileInformation, byte_size: int, sha256: str
    ) -> PredeleteSnapshot:
        volume = hashlib.sha256(
            str(int(information.dwVolumeSerialNumber)).encode("ascii")
        ).hexdigest()
        file_identity = hashlib.sha256(
            (
                str(int(information.dwVolumeSerialNumber))
                + ":"
                + str(int(information.nFileIndexHigh))
                + ":"
                + str(int(information.nFileIndexLow))
            ).encode("ascii")
        ).hexdigest()
        return PredeleteSnapshot(byte_size, sha256, volume, file_identity)

    def _verify_target(
        self, handle: int, target: LocalDeletionTarget
    ) -> tuple[_ByHandleFileInformation, PredeleteSnapshot]:
        information = self._information(handle)
        if information.dwFileAttributes & (0x400 | 0x10):
            raise DeletionBlocked("TARGET_FILESYSTEM_TYPE_INVALID")
        if int(information.nNumberOfLinks) != 1:
            raise DeletionBlocked("TARGET_MULTIPLE_LINKS")
        byte_size, digest = self._hash_handle(handle)
        if byte_size != target.expected_byte_size:
            raise DeletionBlocked("TARGET_SIZE_MISMATCH")
        if digest != target.expected_sha256:
            raise DeletionBlocked("TARGET_HASH_MISMATCH")
        return information, self._identity_snapshot(information, byte_size, digest)

    @staticmethod
    def _same_identity(
        first: _ByHandleFileInformation, second: _ByHandleFileInformation
    ) -> bool:
        return (
            int(first.dwVolumeSerialNumber),
            int(first.nFileIndexHigh),
            int(first.nFileIndexLow),
            int(first.nNumberOfLinks),
            int(first.nFileSizeHigh),
            int(first.nFileSizeLow),
        ) == (
            int(second.dwVolumeSerialNumber),
            int(second.nFileIndexHigh),
            int(second.nFileIndexLow),
            int(second.nNumberOfLinks),
            int(second.nFileSizeHigh),
            int(second.nFileSizeLow),
        )

    def delete(
        self,
        target: LocalDeletionTarget,
        *,
        on_verified: Callable[[PredeleteSnapshot], None],
    ) -> DeletionOutcome:
        if target.root_scope not in {"RESEARCH_ROOT", "EXPORT_STAGING"}:
            raise DeletionBlocked("TARGET_ROOT_SCOPE_INVALID")
        if target.expected_byte_size < 0 or len(target.expected_sha256) != 64:
            raise DeletionBlocked("TARGET_MANIFEST_INVALID")
        parts = self._relative_parts(target.relative_path)
        base = self.root if target.root_scope == "RESEARCH_ROOT" else self.root / "export-staging"
        expected = base.joinpath(*parts)
        directory_paths = [base]
        current = base
        for part in parts[:-1]:
            current = current / part
            directory_paths.append(current)
        directory_handles: list[int] = []
        target_handle = -1
        disposition_requested = False
        ready_for_absence_check = False
        try:
            for directory in directory_paths:
                handle = self._open(
                    directory,
                    directory=True,
                    desired_access=0x80000000,
                    share=3,
                )
                if not self._same_path(self._final_path(handle), directory.resolve(strict=True)):
                    raise DeletionBlocked("TARGET_PARENT_IDENTITY_CHANGED")
                directory_handles.append(handle)
            target_handle = self._open(
                expected,
                directory=False,
                desired_access=0x80000000 | 0x00010000,
                share=0,
            )
            if not self._same_path(self._final_path(target_handle), expected.resolve(strict=True)):
                raise DeletionBlocked("TARGET_FINAL_PATH_MISMATCH")
            first, snapshot = self._verify_target(target_handle, target)
            if (
                target.required_volume_identity_digest is not None
                or target.required_file_identity_digest is not None
            ) and (
                snapshot.volume_identity_digest
                != target.required_volume_identity_digest
                or snapshot.file_identity_digest != target.required_file_identity_digest
            ):
                raise DeletionBlocked("RECOVERY_TARGET_IDENTITY_CHANGED")
            try:
                on_verified(snapshot)
            except Exception as exc:
                raise DeletionBlocked("VERIFIED_CALLBACK_FAILED") from exc
            second, second_snapshot = self._verify_target(target_handle, target)
            if not self._same_identity(first, second) or second_snapshot != snapshot:
                raise DeletionBlocked("TARGET_IDENTITY_CHANGED")
            disposition = _FileDispositionInfo(1)
            if not self._kernel32.SetFileInformationByHandle(
                target_handle,
                4,
                ctypes.byref(disposition),
                ctypes.sizeof(disposition),
            ):
                raise DeletionBlocked("TARGET_DISPOSITION_FAILED")
            disposition_requested = True
            ready_for_absence_check = True
        except DeletionBlocked:
            raise
        except OSError as exc:
            raise DeletionBlocked(
                "TARGET_FILESYSTEM_OPERATION_FAILED",
                disposition_may_have_occurred=disposition_requested,
            ) from exc
        finally:
            if target_handle >= 0:
                self._kernel32.CloseHandle(target_handle)
            if not ready_for_absence_check:
                for handle in reversed(directory_handles):
                    self._kernel32.CloseHandle(handle)
        try:
            if self._before_absence_check is not None:
                try:
                    self._before_absence_check(expected.parent)
                except Exception as exc:
                    raise DeletionBlocked(
                        "ABSENCE_VERIFICATION_HOOK_FAILED",
                        disposition_may_have_occurred=disposition_requested,
                    ) from exc
            try:
                metadata = expected.lstat()
            except FileNotFoundError:
                return DeletionOutcome(target.target_id, True)
            if stat.S_ISREG(metadata.st_mode):
                raise DeletionBlocked(
                    "TARGET_REPLACED_OR_STILL_PRESENT",
                    disposition_may_have_occurred=disposition_requested,
                )
            raise DeletionBlocked(
                "TARGET_ABSENCE_UNVERIFIED",
                disposition_may_have_occurred=disposition_requested,
            )
        finally:
            for handle in reversed(directory_handles):
                self._kernel32.CloseHandle(handle)


class ReconciliationCoordinator:
    """One bounded local run; no startup or implicit retry entry point exists."""

    def __init__(
        self,
        store: ResearchStoreV3,
        *,
        primitive: WindowsHandleDeletionPrimitive | None = None,
        clock: Callable[[], float] = time.time,
        fault_hook: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.planner = ReconciliationPlanner(store)
        self.primitive = primitive or WindowsHandleDeletionPrimitive(store.root)
        self.clock = clock
        self._fault_hook = fault_hook

    def _fault(self, stage: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(stage)

    def authority_binding(self, consumed: ConsumedChallenge) -> ExecutionAuthorityBinding:
        if consumed.execution_kind != "LOCAL_RUN" or consumed.target_id is not None:
            raise ReconciliationBlocked("LOCAL_EXECUTION_BINDING_INVALID")
        plan = self._plan_for_consumed(consumed)
        targets = cast(list[dict[str, object]], plan.body["targets"])
        target_ids = tuple(
            sorted(
                str(target["target_id"])
                for target in targets
                if target["target_kind"]
                in {"LOCAL_RESEARCH_FILE", "LOCAL_EXPORT_STAGING_FILE"}
                and target["state"] in {"PENDING_CONFIRMATION", "RECOVERY_REQUIRED"}
            )
        )
        if not target_ids:
            raise ReconciliationBlocked("NO_LOCAL_TARGET_REQUIRES_RECONCILIATION")
        for target in targets:
            if (
                str(target["target_id"]) in target_ids
                and target["state"] == "RECOVERY_REQUIRED"
                and self._recovery_snapshot(str(target["target_id"])) is None
            ):
                raise ReconciliationBlocked("RECOVERY_SNAPSHOT_REQUIRED")
        return ExecutionAuthorityBinding(
            root_identity_digest=_root_identity_digest(self.store.root),
            execution_id=consumed.execution_id,
            plan_sha256=consumed.plan_sha256,
            target_ids=target_ids,
        )

    def _recovery_snapshot(self, target_id: str) -> PredeleteSnapshot | None:
        row = self.store.connection.execute(
            "SELECT observed_byte_size,observed_sha256,volume_identity_digest,"
            "file_identity_digest FROM reconciliation_attempts "
            "WHERE target_id=? AND stage='RECOVERY_REQUIRED' "
            "AND observed_byte_size IS NOT NULL AND observed_sha256 IS NOT NULL "
            "AND volume_identity_digest IS NOT NULL AND file_identity_digest IS NOT NULL "
            "ORDER BY attempt_number DESC LIMIT 1",
            (target_id,),
        ).fetchone()
        if row is None:
            return None
        return PredeleteSnapshot(
            byte_size=int(row["observed_byte_size"]),
            sha256=str(row["observed_sha256"]),
            volume_identity_digest=str(row["volume_identity_digest"]),
            file_identity_digest=str(row["file_identity_digest"]),
        )

    def _plan_for_consumed(self, consumed: ConsumedChallenge):  # type: ignore[no-untyped-def]
        session = self.store.connection.execute(
            "SELECT subject_session_id FROM withdrawal_receipts WHERE id=? AND participant_id=?",
            (consumed.withdrawal_receipt_id, consumed.participant_id),
        ).fetchone()
        if session is None:
            raise ReconciliationBlocked("WITHDRAWAL_BINDING_INVALID")
        plan = self.planner.plan_for_session(str(session["subject_session_id"]))
        if plan.plan_sha256 != consumed.plan_sha256:
            raise ReconciliationBlocked("PLAN_CHANGED")
        if any(
            code != "RECOVERY_REQUIRED"
            for code in cast(list[str], plan.body["blocker_codes"])
        ):
            raise ReconciliationBlocked("PLAN_BLOCKED")
        return plan

    def run_local(
        self,
        consumed: ConsumedChallenge,
        *,
        authority: ExecutionAuthority | None,
    ) -> dict[str, object]:
        with self.store._root_lock:
            binding = self.authority_binding(consumed)
            if authority is None or not authority.permits_execution(
                root_identity_digest=binding.root_identity_digest,
                execution_id=binding.execution_id,
                plan_sha256=binding.plan_sha256,
                target_ids=binding.target_ids,
            ):
                raise ReconciliationAuthorityNotIssued("AUTHORITY_NOT_ISSUED")
            now = self.clock()
            run_id = "run-" + token_urlsafe(18)
            with self.store.transaction() as connection:
                execution = connection.execute(
                    "SELECT e.execution_kind,c.status,c.action,c.plan_sha256,c.participant_id "
                    "FROM reconciliation_executions e "
                    "JOIN reconciliation_challenges c ON c.id=e.challenge_id "
                    "WHERE e.id=? AND e.challenge_id=?",
                    (consumed.execution_id, consumed.challenge_id),
                ).fetchone()
                if (
                    execution is None
                    or execution["execution_kind"] != "LOCAL_RUN"
                    or execution["status"] != "CONSUMED"
                    or execution["action"] != "EXECUTE_LOCAL_RECONCILIATION"
                    or execution["plan_sha256"] != consumed.plan_sha256
                    or execution["participant_id"] != consumed.participant_id
                ):
                    raise ReconciliationBlocked("LOCAL_EXECUTION_BINDING_INVALID")
                existing = connection.execute(
                    "SELECT id,state FROM reconciliation_runs WHERE execution_id=?",
                    (consumed.execution_id,),
                ).fetchone()
                if existing is not None:
                    return {"run_id": str(existing["id"]), "state": str(existing["state"])}
                connection.execute(
                    "INSERT INTO reconciliation_runs("
                    "id,execution_id,execution_kind,participant_id,challenge_id,plan_sha256,"
                    "state,failure_code,created_at,started_at,terminal_at) "
                    "VALUES(?,?,'LOCAL_RUN',?,?,?,'RUNNING',NULL,?,?,NULL)",
                    (
                        run_id,
                        consumed.execution_id,
                        consumed.participant_id,
                        consumed.challenge_id,
                        consumed.plan_sha256,
                        now,
                        now,
                    ),
                )
                placeholders = ",".join("?" for _ in binding.target_ids)
                connection.execute(
                    "UPDATE withdrawal_task_targets SET state='IN_PROGRESS',"
                    "state_version=state_version+1,blocker_code=NULL,updated_at=? "
                    f"WHERE target_id IN ({placeholders}) "
                    "AND state IN ('PENDING_CONFIRMATION','RECOVERY_REQUIRED')",
                    (now, *binding.target_ids),
                )
            self._fault("after_run_created")
            for target_id in binding.target_ids:
                self._run_target(run_id, target_id)
            terminal_at = self.clock()
            with self.store.transaction() as connection:
                connection.execute(
                    "UPDATE reconciliation_runs SET state='COMPLETED',terminal_at=? WHERE id=?",
                    (terminal_at, run_id),
                )
            return {"run_id": run_id, "state": "COMPLETED"}

    def _run_target(self, run_id: str, target_id: str) -> None:
        now = self.clock()
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT wtt.withdrawal_task_id,rt.target_kind,rt.root_scope,rt.relative_path,"
                "rt.expected_byte_size,rt.expected_sha256 FROM withdrawal_task_targets wtt "
                "JOIN reconciliation_targets rt ON rt.id=wtt.target_id "
                "WHERE wtt.target_id=? AND wtt.state='IN_PROGRESS'",
                (target_id,),
            ).fetchone()
            if row is None or row["target_kind"] not in {
                "LOCAL_RESEARCH_FILE",
                "LOCAL_EXPORT_STAGING_FILE",
            }:
                raise ReconciliationBlocked("LOCAL_TARGET_BINDING_INVALID")
            attempt_number = int(
                connection.execute(
                    "SELECT COALESCE(MAX(attempt_number),0)+1 FROM reconciliation_attempts "
                    "WHERE withdrawal_task_id=? AND target_id=?",
                    (row["withdrawal_task_id"], target_id),
                ).fetchone()[0]
            )
            attempt_id = "attempt-" + token_urlsafe(18)
            connection.execute(
                "INSERT INTO reconciliation_attempts("
                "id,run_id,withdrawal_task_id,target_id,attempt_number,stage,"
                "observed_byte_size,observed_sha256,volume_identity_digest,"
                "file_identity_digest,failure_code,created_at,updated_at) "
                "VALUES(?,?,?,?,?,'PREDELETE_PENDING',NULL,NULL,NULL,NULL,NULL,?,?)",
                (
                    attempt_id,
                    run_id,
                    row["withdrawal_task_id"],
                    target_id,
                    attempt_number,
                    now,
                    now,
                ),
            )
        recovery_snapshot = self._recovery_snapshot(target_id)
        target = LocalDeletionTarget(
            target_id=target_id,
            root_scope=str(row["root_scope"]),
            relative_path=str(row["relative_path"]),
            expected_byte_size=int(row["expected_byte_size"]),
            expected_sha256=str(row["expected_sha256"]),
            required_volume_identity_digest=(
                None
                if recovery_snapshot is None
                else recovery_snapshot.volume_identity_digest
            ),
            required_file_identity_digest=(
                None if recovery_snapshot is None else recovery_snapshot.file_identity_digest
            ),
        )

        def verified(snapshot: PredeleteSnapshot) -> None:
            with self.store.transaction() as connection:
                connection.execute(
                    "UPDATE reconciliation_attempts SET stage='PREDELETE_VERIFIED',"
                    "observed_byte_size=?,observed_sha256=?,volume_identity_digest=?,"
                    "file_identity_digest=?,updated_at=? WHERE id=?",
                    (
                        snapshot.byte_size,
                        snapshot.sha256,
                        snapshot.volume_identity_digest,
                        snapshot.file_identity_digest,
                        self.clock(),
                        attempt_id,
                    ),
                )

        try:
            outcome = self.primitive.delete(target, on_verified=verified)
        except DeletionBlocked as exc:
            state = "RECOVERY_REQUIRED" if exc.disposition_may_have_occurred else "BLOCKED"
            stage = state
            with self.store.transaction() as connection:
                connection.execute(
                    "UPDATE reconciliation_attempts SET stage=?,failure_code=?,updated_at=? "
                    "WHERE id=?",
                    (stage, exc.code, self.clock(), attempt_id),
                )
                connection.execute(
                    "UPDATE withdrawal_task_targets SET state=?,state_version=state_version+1,"
                    "blocker_code=?,updated_at=? WHERE target_id=?",
                    (state, exc.code, self.clock(), target_id),
                )
                connection.execute(
                    "UPDATE reconciliation_runs SET state=?,failure_code=?,terminal_at=? "
                    "WHERE id=?",
                    (state, exc.code, self.clock(), run_id),
                )
            raise
        if not outcome.absence_verified:
            raise DeletionBlocked("TARGET_ABSENCE_UNVERIFIED", disposition_may_have_occurred=True)
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE reconciliation_attempts SET stage='ABSENCE_VERIFIED',updated_at=? "
                "WHERE id=? AND stage='PREDELETE_VERIFIED'",
                (self.clock(), attempt_id),
            )
            connection.execute(
                "UPDATE withdrawal_task_targets SET state='LOCAL_DELETION_VERIFIED',"
                "state_version=state_version+1,blocker_code=NULL,updated_at=? "
                "WHERE target_id=? AND state='IN_PROGRESS'",
                (self.clock(), target_id),
            )


class ReconciliationFinalizer:
    """Persist one canonical receipt only after kind-specific evidence re-joins."""

    def __init__(self, store: ResearchStoreV3) -> None:
        self.store = store
        self.planner = ReconciliationPlanner(store)

    def _existing(self, session_id: str) -> ReconciliationReceipt | None:
        with self.store._lock:
            row = self.store.connection.execute(
                "SELECT rr.body_json,rr.body_sha256 FROM sessions s "
                "JOIN reconciliation_receipts rr ON rr.participant_id=s.participant_id "
                "WHERE s.id=?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            body = json.loads(str(row["body_json"]))
        except json.JSONDecodeError as exc:
            raise SchemaIntegrityError("reconciliation receipt is malformed") from exc
        if not isinstance(body, dict):
            raise SchemaIntegrityError("reconciliation receipt is malformed")
        canonical = json.dumps(
            body,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if canonical != row["body_json"] or digest != row["body_sha256"]:
            raise SchemaIntegrityError("reconciliation receipt binding is invalid")
        return ReconciliationReceipt(
            body={str(key): value for key, value in body.items()},
            canonical_json=canonical,
            body_sha256=digest,
        )

    @staticmethod
    def _require_terminal_evidence(
        connection: sqlite3.Connection, plan: ReconciliationPlan
    ) -> None:
        targets = cast(list[dict[str, object]], plan.body["targets"])
        for target in targets:
            target_id = str(target["target_id"])
            if target["target_kind"] == "EXTERNAL_COPY":
                evidence = connection.execute(
                    "SELECT 1 FROM external_deletion_attestations a "
                    "JOIN reconciliation_executions e ON e.id=a.execution_id "
                    "AND e.challenge_id=a.challenge_id "
                    "JOIN reconciliation_challenges c ON c.id=a.challenge_id "
                    "JOIN approved_procedure_authorities p "
                    "ON p.id=a.procedure_authority_id "
                    "WHERE a.target_id=? AND a.participant_id=? "
                    "AND a.withdrawal_receipt_id=? "
                    "AND c.plan_sha256=a.plan_sha256 "
                    "AND c.participant_id=a.participant_id "
                    "AND c.withdrawal_receipt_id=a.withdrawal_receipt_id "
                    "AND c.target_id=a.target_id "
                    "AND a.target_kind='EXTERNAL_COPY' "
                    "AND a.root_scope='EXTERNAL_ATTESTATION' "
                    "AND a.challenge_action='ATTEST_EXTERNAL_DELETION' "
                    "AND e.execution_kind='EXTERNAL_ATTESTATION' "
                    "AND c.action='ATTEST_EXTERNAL_DELETION' AND c.status='CONSUMED' "
                    "AND p.procedure_kind='EXTERNAL_DELETION' "
                    "AND p.status='APPROVED' AND p.revoked_at IS NULL "
                    "AND p.approved_at<=? AND (p.expires_at IS NULL OR p.expires_at>?)",
                    (
                        target_id,
                        plan.participant_id,
                        plan.withdrawal_receipt_id,
                        time.time(),
                        time.time(),
                    ),
                ).fetchone()
            else:
                evidence = connection.execute(
                    "SELECT 1 FROM reconciliation_attempts a "
                    "JOIN reconciliation_runs r ON r.id=a.run_id "
                    "JOIN reconciliation_executions e ON e.id=r.execution_id "
                    "AND e.challenge_id=r.challenge_id "
                    "JOIN reconciliation_challenges c ON c.id=r.challenge_id "
                    "WHERE a.target_id=? AND a.stage='ABSENCE_VERIFIED' "
                    "AND r.participant_id=? AND r.state='COMPLETED' "
                    "AND c.plan_sha256=r.plan_sha256 "
                    "AND c.participant_id=r.participant_id "
                    "AND c.withdrawal_receipt_id=? AND c.target_id IS NULL "
                    "AND e.execution_kind='LOCAL_RUN' "
                    "AND c.action='EXECUTE_LOCAL_RECONCILIATION' "
                    "AND c.status='CONSUMED'",
                    (
                        target_id,
                        plan.participant_id,
                        plan.withdrawal_receipt_id,
                    ),
                ).fetchone()
            if evidence is None:
                raise ReconciliationBlocked("TERMINAL_EVIDENCE_BINDING_INVALID")

    def finalize(self, session_id: str) -> ReconciliationReceipt:
        with self.store._root_lock:
            plan = self.planner.plan_for_session(session_id)
            existing = self._existing(session_id)
            if not bool(plan.body["complete"]):
                if existing is not None:
                    raise SchemaIntegrityError("reconciliation receipt state is invalid")
                raise ReconciliationBlocked("RECONCILIATION_NOT_COMPLETE")
            receipt = ReconciliationReceipt.from_plan(plan)
            with self.store.transaction() as connection:
                self._require_terminal_evidence(connection, plan)
                if existing is not None:
                    if (
                        existing.canonical_json != receipt.canonical_json
                        or existing.body_sha256 != receipt.body_sha256
                    ):
                        raise SchemaIntegrityError(
                            "reconciliation receipt replay binding is invalid"
                        )
                    return existing
                connection.execute(
                    "UPDATE withdrawal_tasks SET status='COMPLETED' WHERE id IN ("
                    "SELECT wtt.withdrawal_task_id FROM withdrawal_task_targets wtt "
                    "WHERE wtt.participant_id=? GROUP BY wtt.withdrawal_task_id "
                    "HAVING SUM(CASE WHEN "
                    "(wtt.target_kind='EXTERNAL_COPY' "
                    "AND wtt.state='EXTERNAL_DELETION_ATTESTED') OR "
                    "(wtt.target_kind<>'EXTERNAL_COPY' "
                    "AND wtt.state='LOCAL_DELETION_VERIFIED') THEN 0 ELSE 1 END)=0)",
                    (plan.participant_id,),
                )
                receipt_id = "reconciliation-receipt-" + receipt.body_sha256[:24]
                connection.execute(
                    "INSERT INTO reconciliation_receipts("
                    "id,participant_id,withdrawal_receipt_id,body_json,body_sha256,created_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        receipt_id,
                        plan.participant_id,
                        plan.withdrawal_receipt_id,
                        receipt.canonical_json,
                        receipt.body_sha256,
                        time.time(),
                    ),
                )
            return receipt
