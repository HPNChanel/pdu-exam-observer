"""Closed signed-A0 verification boundary for D1-N2.

Production is intentionally unprovisioned.  This module never creates keys,
signatures, approval files, paths, or network transports.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn, Protocol

A0_VALIDITY_NS = 900_000_000_000
A0_DOMAIN = "D1N2/A0_APPROVAL/v1"
A0_SIGNATURE_ALGORITHM = "ECDSA_P256_SHA256_IEEE_P1363"
A0_AUTHORITY_REVISION = "d1-n2-authority-v1"
_MAX_SIGNED_NS = (1 << 63) - 1


class BootstrapStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNPROVISIONED = "UNPROVISIONED"
    REJECTED = "REJECTED"


class A0VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    BOOTSTRAP_UNPROVISIONED = "BOOTSTRAP_UNPROVISIONED"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


@dataclass(frozen=True, slots=True)
class ApprovedRP2Triple:
    static_bindings_digest: str
    binding_schema_canonical_sha256: str
    candidate_exact_bytes_sha256: str
    a0_approval_digest: str
    approval_id_digest: str
    issued_unix_ns: int
    expires_unix_ns: int

    def valid(self) -> bool:
        return (
            all(
                _is_digest(value)
                for value in (
                    self.static_bindings_digest,
                    self.binding_schema_canonical_sha256,
                    self.candidate_exact_bytes_sha256,
                    self.a0_approval_digest,
                    self.approval_id_digest,
                )
            )
            and type(self.issued_unix_ns) is int
            and type(self.expires_unix_ns) is int
            and 0 <= self.issued_unix_ns <= _MAX_SIGNED_NS - A0_VALIDITY_NS
            and self.expires_unix_ns - self.issued_unix_ns == A0_VALIDITY_NS
        )

    def pending_fields(self) -> dict[str, object]:
        return {
            "a0_approval_digest": self.a0_approval_digest,
            "approval_id_digest": self.approval_id_digest,
            "binding_schema_canonical_sha256": self.binding_schema_canonical_sha256,
            "candidate_exact_bytes_sha256": self.candidate_exact_bytes_sha256,
            "expires_unix_ns": self.expires_unix_ns,
            "issued_unix_ns": self.issued_unix_ns,
            "static_bindings_digest": self.static_bindings_digest,
        }


class A0ApprovalLease(Protocol):
    def read_exact(self) -> bytes: ...

    def validate(self) -> bool: ...

    def parent_durable(self) -> bool: ...

    def close(self) -> bool: ...


class A0ApprovalSource(Protocol):
    def open_fixed(self) -> A0ApprovalLease: ...


class A0BootstrapPort(Protocol):
    def inspect(self) -> BootstrapStatus: ...

    def verify(
        self, canonical_body: bytes, key_id: str, signature: bytes
    ) -> BootstrapStatus: ...

    def validate(self) -> bool: ...

    def close(self) -> bool: ...


class UnprovisionedA0Bootstrap:
    """Production bootstrap until a separate provisioning receipt is approved."""

    __slots__ = ()

    def inspect(self) -> BootstrapStatus:
        return BootstrapStatus.UNPROVISIONED

    def verify(
        self, canonical_body: bytes, key_id: str, signature: bytes
    ) -> BootstrapStatus:
        del canonical_body, key_id, signature
        return BootstrapStatus.UNPROVISIONED

    def validate(self) -> bool:
        return False

    def close(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class A0VerificationResult:
    status: A0VerificationStatus
    approved: ApprovedRP2Triple | None = None
    lease: A0ApprovalLease | None = None
    bootstrap: A0BootstrapPort | None = None


_ROOT_KEYS = {
    "body",
    "domain",
    "key_id",
    "schema_version",
    "signature_algorithm",
    "signature_b64url",
}
_BODY_KEYS = {
    "approval_id_digest",
    "audio_authorized",
    "authority_revision",
    "binding_schema_canonical_sha256",
    "candidate_exact_bytes_sha256",
    "duration_seconds",
    "expires_unix_ns",
    "issued_unix_ns",
    "model_training_or_evaluation_authorized",
    "network_authorized",
    "no_human",
    "participant_collection_authorized",
    "raw_retention_authorized",
    "retry_authorized",
    "static_bindings_digest",
    "video_only",
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _is_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _decode_closed(payload: bytes) -> dict[str, object] | None:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_number(_value: str) -> NoReturn:
        raise ValueError("non-integer number")

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=reject_number,
            parse_constant=reject_number,
        )
    except (TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    if type(value) is not dict or _canonical_bytes(value) != payload:
        return None
    return value


def _signature(value: object) -> bytes | None:
    if type(value) is not str or "=" in value or len(value) != 86:
        return None
    try:
        decoded = base64.urlsafe_b64decode(value + "==")
    except (ValueError, TypeError):
        return None
    if len(decoded) != 64:
        return None
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        return None
    return decoded


def _scope_valid(body: dict[str, object]) -> bool:
    return (
        set(body) == _BODY_KEYS
        and body.get("authority_revision") == A0_AUTHORITY_REVISION
        and body.get("no_human") is True
        and body.get("video_only") is True
        and type(body.get("duration_seconds")) is int
        and body.get("duration_seconds") == 60
        and body.get("retry_authorized") is False
        and body.get("audio_authorized") is False
        and body.get("network_authorized") is False
        and body.get("raw_retention_authorized") is False
        and body.get("participant_collection_authorized") is False
        and body.get("model_training_or_evaluation_authorized") is False
        and all(
            _is_digest(body.get(name))
            for name in (
                "static_bindings_digest",
                "binding_schema_canonical_sha256",
                "candidate_exact_bytes_sha256",
                "approval_id_digest",
            )
        )
    )


class FixedA0Verifier:
    """Verify one fixed installed approval without providing installation powers."""

    def __init__(
        self,
        source: A0ApprovalSource,
        bootstrap: A0BootstrapPort,
        unix_clock_ns: Callable[[], int],
    ) -> None:
        self._source = source
        self._bootstrap = bootstrap
        self._unix_clock_ns = unix_clock_ns

    @classmethod
    def production_unprovisioned(
        cls,
        source: A0ApprovalSource,
        unix_clock_ns: Callable[[], int],
    ) -> FixedA0Verifier:
        return cls(source, UnprovisionedA0Bootstrap(), unix_clock_ns)

    @staticmethod
    def _failed(
        status: A0VerificationStatus,
        lease: A0ApprovalLease | None,
        bootstrap: A0BootstrapPort,
    ) -> A0VerificationResult:
        clean = True
        if lease is not None:
            try:
                clean = lease.close() and clean
            except BaseException:
                clean = False
        try:
            clean = bootstrap.close() and clean
        except BaseException:
            clean = False
        return A0VerificationResult(
            status if clean else A0VerificationStatus.CLEANUP_FAILED,
            bootstrap=bootstrap,
        )

    def verify(self) -> A0VerificationResult:
        try:
            bootstrap_status = self._bootstrap.inspect()
        except BaseException:
            bootstrap_status = BootstrapStatus.REJECTED
        if bootstrap_status is BootstrapStatus.UNPROVISIONED:
            return self._failed(
                A0VerificationStatus.BOOTSTRAP_UNPROVISIONED,
                None,
                self._bootstrap,
            )
        if bootstrap_status is not BootstrapStatus.VERIFIED:
            return self._failed(
                A0VerificationStatus.INVALID,
                None,
                self._bootstrap,
            )
        lease: A0ApprovalLease | None = None
        try:
            lease = self._source.open_fixed()
            payload = lease.read_exact()
            lease_valid = lease.validate()
            parent_durable = lease.parent_durable()
        except BaseException:
            if lease is not None:
                return self._failed(
                    A0VerificationStatus.INVALID,
                    lease,
                    self._bootstrap,
                )
            return self._failed(
                A0VerificationStatus.INVALID,
                None,
                self._bootstrap,
            )
        if type(payload) is not bytes or not lease_valid or not parent_durable:
            return self._failed(A0VerificationStatus.INVALID, lease, self._bootstrap)
        root = _decode_closed(payload)
        if (
            root is None
            or set(root) != _ROOT_KEYS
            or type(root.get("schema_version")) is not int
            or root.get("schema_version") != 1
            or root.get("domain") != A0_DOMAIN
            or root.get("signature_algorithm") != A0_SIGNATURE_ALGORITHM
            or not _is_digest(root.get("key_id"))
            or type(root.get("body")) is not dict
        ):
            return self._failed(A0VerificationStatus.INVALID, lease, self._bootstrap)
        body = root["body"]
        assert isinstance(body, dict)
        signature = _signature(root.get("signature_b64url"))
        if signature is None or not _scope_valid(body):
            return self._failed(A0VerificationStatus.INVALID, lease, self._bootstrap)
        issued = body.get("issued_unix_ns")
        expires = body.get("expires_unix_ns")
        try:
            now = self._unix_clock_ns()
        except BaseException:
            return self._failed(A0VerificationStatus.INVALID, lease, self._bootstrap)
        if (
            type(issued) is not int
            or type(expires) is not int
            or type(now) is not int
            or issued < 0
            or issued > _MAX_SIGNED_NS - A0_VALIDITY_NS
            or expires - issued != A0_VALIDITY_NS
            or now < issued
        ):
            return self._failed(A0VerificationStatus.INVALID, lease, self._bootstrap)
        if now > expires:
            return self._failed(A0VerificationStatus.EXPIRED, lease, self._bootstrap)
        canonical_body = _canonical_bytes(body)
        try:
            bootstrap_status = self._bootstrap.verify(
                canonical_body,
                str(root["key_id"]),
                signature,
            )
        except BaseException:
            bootstrap_status = BootstrapStatus.REJECTED
        if bootstrap_status is BootstrapStatus.UNPROVISIONED:
            return self._failed(
                A0VerificationStatus.BOOTSTRAP_UNPROVISIONED,
                lease,
                self._bootstrap,
            )
        if bootstrap_status is not BootstrapStatus.VERIFIED:
            return self._failed(A0VerificationStatus.INVALID, lease, self._bootstrap)
        approved = ApprovedRP2Triple(
            static_bindings_digest=str(body["static_bindings_digest"]),
            binding_schema_canonical_sha256=str(
                body["binding_schema_canonical_sha256"]
            ),
            candidate_exact_bytes_sha256=str(body["candidate_exact_bytes_sha256"]),
            a0_approval_digest=hashlib.sha256(payload).hexdigest(),
            approval_id_digest=str(body["approval_id_digest"]),
            issued_unix_ns=issued,
            expires_unix_ns=expires,
        )
        if (
            not approved.valid()
            or not lease.validate()
            or not self._bootstrap.validate()
        ):
            return self._failed(A0VerificationStatus.INVALID, lease, self._bootstrap)
        return A0VerificationResult(
            A0VerificationStatus.VERIFIED,
            approved,
            lease,
            self._bootstrap,
        )


__all__ = [
    "A0ApprovalLease",
    "A0ApprovalSource",
    "A0BootstrapPort",
    "A0VerificationResult",
    "A0VerificationStatus",
    "ApprovedRP2Triple",
    "BootstrapStatus",
    "FixedA0Verifier",
    "UnprovisionedA0Bootstrap",
]
