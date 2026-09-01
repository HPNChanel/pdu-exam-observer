"""Bounded reviewer service for source-only synthetic M2 runs."""

from __future__ import annotations

import hashlib
import re
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Self

from pdu_exam_observer.m1 import M1Backend
from pdu_exam_observer.m2_d1_contract import PrivacyDecision
from pdu_exam_observer.m2_persistence import M2PersistenceStore, PlatformUnsupported
from pdu_exam_observer.m2_synthetic_environment import current_synthetic_environment_bindings
from pdu_exam_observer.m2_synthetic_evidence import (
    MAX_EVIDENCE_BYTES,
    SyntheticEvidenceError,
    SyntheticEvidenceExport,
    build_synthetic_evidence_bundle,
)
from pdu_exam_observer.m2_synthetic_integration import (
    IntegrationStatus,
    M2SyntheticNominalCore,
    M2SyntheticPreflightCore,
    SyntheticIntegrationReceipt,
    SyntheticNominalRequest,
    SyntheticPreflightRequest,
)
from pdu_exam_observer.m2_synthetic_nominal_fixture import (
    BUILTIN_RUN_ID as NOMINAL_RUN_ID,
)
from pdu_exam_observer.m2_synthetic_nominal_fixture import (
    build_builtin_nominal_bundle,
)
from pdu_exam_observer.m2_synthetic_preflight_fixture import (
    BUILTIN_RUN_ID as PREFLIGHT_RUN_ID,
)
from pdu_exam_observer.m2_synthetic_preflight_fixture import (
    build_builtin_preflight_bundle,
)

_KEY = re.compile(r"[A-Za-z0-9._-]{16,128}\Z")


class SyntheticReviewRunKind(StrEnum):
    PREFLIGHT_60S = "PREFLIGHT_60S"
    NOMINAL_20M = "NOMINAL_20M"


class SyntheticReviewJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    TERMINAL = "TERMINAL"


class SyntheticReviewServiceFailureCode(StrEnum):
    SERVICE_CLOSED = "SERVICE_CLOSED"
    RUN_ALREADY_ACTIVE = "RUN_ALREADY_ACTIVE"
    CAPACITY_EXHAUSTED = "CAPACITY_EXHAUSTED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    EVIDENCE_NOT_EXPORTABLE = "EVIDENCE_NOT_EXPORTABLE"
    EVIDENCE_INTEGRITY_FAILED = "EVIDENCE_INTEGRITY_FAILED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


class SyntheticReviewServiceError(RuntimeError):
    def __init__(self, code: SyntheticReviewServiceFailureCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class SyntheticReviewRunRecord:
    schema_version: int
    request_id: str
    run_sequence: int
    run_kind: SyntheticReviewRunKind
    job_status: SyntheticReviewJobStatus
    service_failure_code: SyntheticReviewServiceFailureCode | None
    receipt: SyntheticIntegrationReceipt | None

    def as_dict(self) -> dict[str, object]:
        return {
            "job_status": self.job_status.value,
            "receipt": self.receipt.as_dict() if self.receipt is not None else None,
            "request_id": self.request_id,
            "run_kind": self.run_kind.value,
            "run_sequence": self.run_sequence,
            "schema_version": self.schema_version,
            "service_failure_code": (
                self.service_failure_code.value if self.service_failure_code is not None else None
            ),
        }


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


RunCallable = Callable[[str], SyntheticIntegrationReceipt]
ArtifactReader = Callable[[str, int], bytes]


class SyntheticReviewService:
    MAX_RECORDS = 32

    def __init__(
        self,
        *,
        preflight: RunCallable,
        nominal: RunCallable,
        temporary: tempfile.TemporaryDirectory[str],
        store: M2PersistenceStore | None,
        artifact_reader: ArtifactReader | None,
        max_records: int = MAX_RECORDS,
    ) -> None:
        self._preflight = preflight
        self._nominal = nominal
        self._temporary = temporary
        self._root = Path(temporary.name)
        self._store = store
        self._artifact_reader = artifact_reader
        self._max_records = max_records
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdu-m2-synthetic")
        self._lock = RLock()
        self._records: dict[str, SyntheticReviewRunRecord] = {}
        self._key_digests: dict[str, str] = {}
        self._active_request_id: str | None = None
        self._sequence = 0
        self._closed = False

    @classmethod
    def create_owned(cls) -> Self:
        temporary = tempfile.TemporaryDirectory(prefix="pdu-m2-s2c-")
        backend: M1Backend | None = None
        store: M2PersistenceStore | None = None
        try:
            root = Path(temporary.name)
            backend = M1Backend(root, encryption_status="UNVERIFIED", acl_status="UNVERIFIED")
            study = backend.create_study("m2-s2c", idempotency_key="study-m2-s2c")
            participant = backend.create_participant(
                str(study["study_id"]), idempotency_key="participant-m2-s2c"
            )
            session = backend.create_research_session(
                str(study["study_id"]),
                str(participant["participant_id"]),
                idempotency_key="session-m2-s2c",
                retention_policy_reference="synthetic-service-lifetime-only",
            )
            session_id = str(session["session_id"])
            backend.store.close()
            backend = None
            store = M2PersistenceStore(root)
            bindings = current_synthetic_environment_bindings()

            def preflight(request_id: str) -> SyntheticIntegrationReceipt:
                bundle = build_builtin_preflight_bundle(bindings.pose_engine_digest)
                core = M2SyntheticPreflightCore(
                    runner=bundle.runner,
                    privacy_guard=_Privacy(),
                    owner_lease=_Lease(),
                    persistence_store=store,
                    environment_bindings=bindings,
                )
                return core.execute(
                    SyntheticPreflightRequest(
                        session_id=session_id,
                        intent_id=f"intent-{request_id}",
                        artifact_id=f"artifact-{request_id}",
                        run_id=PREFLIGHT_RUN_ID,
                        fixtures=bundle.fixtures,
                    )
                )

            def nominal(request_id: str) -> SyntheticIntegrationReceipt:
                bundle = build_builtin_nominal_bundle(bindings.pose_engine_digest)
                core = M2SyntheticNominalCore(
                    runner=bundle.runner,
                    privacy_guard=_Privacy(),
                    owner_lease=_Lease(),
                    persistence_store=store,
                    environment_bindings=bindings,
                )
                return core.execute(
                    SyntheticNominalRequest(
                        session_id=session_id,
                        intent_id=f"intent-{request_id}",
                        artifact_id=f"artifact-{request_id}",
                        run_id=NOMINAL_RUN_ID,
                        fixtures=bundle.fixtures,
                    )
                )

            return cls(
                preflight=preflight,
                nominal=nominal,
                temporary=temporary,
                store=store,
                artifact_reader=lambda artifact_id, maximum: store.read_verified_artifact(
                    artifact_id, maximum_bytes=maximum
                ),
            )
        except Exception:
            if store is not None:
                store.close()
            if backend is not None:
                backend.store.close()
            temporary.cleanup()
            raise

    @classmethod
    def _for_tests(
        cls,
        preflight: Callable[[], SyntheticIntegrationReceipt],
        nominal: Callable[[], SyntheticIntegrationReceipt],
        *,
        max_records: int = MAX_RECORDS,
    ) -> Self:
        return cls(
            preflight=lambda _request_id: preflight(),
            nominal=lambda _request_id: nominal(),
            temporary=tempfile.TemporaryDirectory(prefix="pdu-m2-s2c-test-"),
            store=None,
            artifact_reader=None,
            max_records=max_records,
        )

    def submit(
        self,
        run_kind: SyntheticReviewRunKind,
        *,
        idempotency_key: str,
    ) -> SyntheticReviewRunRecord:
        if not isinstance(run_kind, SyntheticReviewRunKind) or not _KEY.fullmatch(idempotency_key):
            raise SyntheticReviewServiceError(
                SyntheticReviewServiceFailureCode.IDEMPOTENCY_CONFLICT
            )
        key_digest = hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
        request_id = f"synrun-{key_digest[:32]}"
        with self._lock:
            if self._closed:
                raise SyntheticReviewServiceError(SyntheticReviewServiceFailureCode.SERVICE_CLOSED)
            previous_id = self._key_digests.get(key_digest)
            if previous_id is not None:
                previous = self._records[previous_id]
                if previous.run_kind is not run_kind:
                    raise SyntheticReviewServiceError(
                        SyntheticReviewServiceFailureCode.IDEMPOTENCY_CONFLICT
                    )
                return previous
            if self._active_request_id is not None:
                raise SyntheticReviewServiceError(
                    SyntheticReviewServiceFailureCode.RUN_ALREADY_ACTIVE
                )
            if len(self._records) >= self._max_records:
                raise SyntheticReviewServiceError(
                    SyntheticReviewServiceFailureCode.CAPACITY_EXHAUSTED
                )
            self._sequence += 1
            record = SyntheticReviewRunRecord(
                schema_version=1,
                request_id=request_id,
                run_sequence=self._sequence,
                run_kind=run_kind,
                job_status=SyntheticReviewJobStatus.QUEUED,
                service_failure_code=None,
                receipt=None,
            )
            self._records[request_id] = record
            self._key_digests[key_digest] = request_id
            self._active_request_id = request_id
            self._executor.submit(self._run, request_id)
            return record

    def _run(self, request_id: str) -> None:
        with self._lock:
            current = self._records[request_id]
            self._records[request_id] = replace(
                current, job_status=SyntheticReviewJobStatus.RUNNING
            )
        try:
            callback = (
                self._preflight
                if current.run_kind is SyntheticReviewRunKind.PREFLIGHT_60S
                else self._nominal
            )
            receipt = callback(request_id)
            terminal = replace(
                current,
                job_status=SyntheticReviewJobStatus.TERMINAL,
                receipt=receipt,
            )
        except PlatformUnsupported:
            terminal = replace(
                current,
                job_status=SyntheticReviewJobStatus.TERMINAL,
                service_failure_code=SyntheticReviewServiceFailureCode.PLATFORM_UNSUPPORTED,
            )
        except Exception:
            terminal = replace(
                current,
                job_status=SyntheticReviewJobStatus.TERMINAL,
                service_failure_code=SyntheticReviewServiceFailureCode.UNEXPECTED_FAILURE,
            )
        with self._lock:
            self._records[request_id] = terminal
            if self._active_request_id == request_id:
                self._active_request_id = None

    def get(self, request_id: str) -> SyntheticReviewRunRecord:
        with self._lock:
            try:
                return self._records[request_id]
            except KeyError as exc:
                raise KeyError(request_id) from exc

    def list(self) -> tuple[SyntheticReviewRunRecord, ...]:
        with self._lock:
            return tuple(
                sorted(self._records.values(), key=lambda item: item.run_sequence, reverse=True)
            )

    def export_evidence(self, request_id: str) -> SyntheticEvidenceExport:
        with self._lock:
            if self._closed:
                raise SyntheticReviewServiceError(SyntheticReviewServiceFailureCode.SERVICE_CLOSED)
            try:
                record = self._records[request_id]
            except KeyError as exc:
                raise KeyError(request_id) from exc
            receipt = record.receipt
            if (
                record.job_status is not SyntheticReviewJobStatus.TERMINAL
                or record.service_failure_code is not None
                or receipt is None
                or receipt.integration_status is not IntegrationStatus.PERSISTED
                or receipt.artifact_id is None
            ):
                raise SyntheticReviewServiceError(
                    SyntheticReviewServiceFailureCode.EVIDENCE_NOT_EXPORTABLE
                )
            if self._artifact_reader is None:
                raise SyntheticReviewServiceError(
                    SyntheticReviewServiceFailureCode.EVIDENCE_INTEGRITY_FAILED
                )
            try:
                artifact = self._artifact_reader(receipt.artifact_id, MAX_EVIDENCE_BYTES)
                return build_synthetic_evidence_bundle(record.as_dict(), artifact)
            except PlatformUnsupported:
                raise
            except SyntheticEvidenceError as exc:
                raise SyntheticReviewServiceError(
                    SyntheticReviewServiceFailureCode.EVIDENCE_INTEGRITY_FAILED
                ) from exc
            except Exception as exc:
                raise SyntheticReviewServiceError(
                    SyntheticReviewServiceFailureCode.EVIDENCE_INTEGRITY_FAILED
                ) from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=False)
        try:
            if self._store is not None:
                self._store.close()
                self._store = None
            self._artifact_reader = None
        finally:
            self._temporary.cleanup()

    def _owned_root_for_test(self) -> Path:
        return self._root
