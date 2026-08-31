from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import replace

from pdu_exam_observer.m2_d1_n2_a0 import (
    A0VerificationStatus,
    BootstrapStatus,
    FixedA0Verifier,
    UnprovisionedA0Bootstrap,
)

NOW_NS = 2_000_000_000_000
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
DIGEST_D = "d" * 64
KEY_ID = "e" * 64
SIGNATURE = bytes(range(64))


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _envelope(*, body_update: dict[str, object] | None = None) -> bytes:
    body: dict[str, object] = {
        "approval_id_digest": DIGEST_D,
        "audio_authorized": False,
        "authority_revision": "d1-n2-authority-v1",
        "binding_schema_canonical_sha256": DIGEST_B,
        "candidate_exact_bytes_sha256": DIGEST_C,
        "duration_seconds": 60,
        "expires_unix_ns": NOW_NS + 900_000_000_000,
        "issued_unix_ns": NOW_NS,
        "model_training_or_evaluation_authorized": False,
        "network_authorized": False,
        "no_human": True,
        "participant_collection_authorized": False,
        "raw_retention_authorized": False,
        "retry_authorized": False,
        "static_bindings_digest": DIGEST_A,
        "video_only": True,
    }
    if body_update:
        body.update(body_update)
    return _canonical(
        {
            "body": body,
            "domain": "D1N2/A0_APPROVAL/v1",
            "key_id": KEY_ID,
            "schema_version": 1,
            "signature_algorithm": "ECDSA_P256_SHA256_IEEE_P1363",
            "signature_b64url": base64.urlsafe_b64encode(SIGNATURE).rstrip(b"=").decode(),
        }
    )


class _Lease:
    def __init__(self, payload: bytes, *, valid: bool = True, durable: bool = True) -> None:
        self.payload = payload
        self.valid = valid
        self.durable = durable
        self.close_calls = 0

    def read_exact(self) -> bytes:
        return self.payload

    def validate(self) -> bool:
        return self.valid

    def parent_durable(self) -> bool:
        return self.durable

    def close(self) -> bool:
        self.close_calls += 1
        return True


class _Source:
    def __init__(self, lease: _Lease, events: list[str] | None = None) -> None:
        self.lease = lease
        self.open_calls = 0
        self.events = events

    def open_fixed(self) -> _Lease:
        self.open_calls += 1
        if self.events is not None:
            self.events.append("source")
        return self.lease


class _Bootstrap:
    def __init__(
        self,
        status: BootstrapStatus = BootstrapStatus.VERIFIED,
        *,
        inspect_status: BootstrapStatus = BootstrapStatus.VERIFIED,
        events: list[str] | None = None,
    ) -> None:
        self.status = status
        self.inspect_status = inspect_status
        self.events = events
        self.inspect_calls = 0
        self.close_calls = 0
        self.valid = True
        self.calls: list[tuple[bytes, str, bytes]] = []

    def inspect(self) -> BootstrapStatus:
        self.inspect_calls += 1
        if self.events is not None:
            self.events.append("inspect")
        return self.inspect_status

    def verify(self, canonical_body: bytes, key_id: str, signature: bytes) -> BootstrapStatus:
        if self.events is not None:
            self.events.append("verify")
        self.calls.append((canonical_body, key_id, signature))
        return self.status

    def validate(self) -> bool:
        return self.valid

    def close(self) -> bool:
        self.close_calls += 1
        return True


def test_valid_envelope_returns_exact_signed_triple_and_retains_lease() -> None:
    payload = _envelope()
    lease = _Lease(payload)
    bootstrap = _Bootstrap()

    result = FixedA0Verifier(_Source(lease), bootstrap, lambda: NOW_NS).verify()

    assert result.status is A0VerificationStatus.VERIFIED
    assert result.lease is lease
    assert result.approved is not None
    assert result.approved.static_bindings_digest == DIGEST_A
    assert result.approved.binding_schema_canonical_sha256 == DIGEST_B
    assert result.approved.candidate_exact_bytes_sha256 == DIGEST_C
    assert result.approved.approval_id_digest == DIGEST_D
    assert result.approved.a0_approval_digest == hashlib.sha256(payload).hexdigest()
    assert bootstrap.calls == [
        (
            _canonical(json.loads(payload)["body"]),
            KEY_ID,
            SIGNATURE,
        )
    ]
    assert lease.close_calls == 0
    assert bootstrap.inspect_calls == 1
    assert bootstrap.close_calls == 0


def test_bootstrap_inspection_precedes_a0_open_and_rejection_never_opens_source() -> None:
    events: list[str] = []
    source = _Source(_Lease(_envelope()), events)
    bootstrap = _Bootstrap(events=events)

    result = FixedA0Verifier(source, bootstrap, lambda: NOW_NS).verify()

    assert result.status is A0VerificationStatus.VERIFIED
    assert events == ["inspect", "source", "verify"]

    events.clear()
    source = _Source(_Lease(_envelope()), events)
    bootstrap = _Bootstrap(
        inspect_status=BootstrapStatus.REJECTED,
        events=events,
    )

    result = FixedA0Verifier(source, bootstrap, lambda: NOW_NS).verify()

    assert result.status is A0VerificationStatus.INVALID
    assert events == ["inspect"]
    assert source.open_calls == 0
    assert bootstrap.close_calls == 1


def test_production_unprovisioned_bootstrap_does_not_open_approval_source() -> None:
    source = _Source(_Lease(_envelope()))

    result = FixedA0Verifier.production_unprovisioned(source, lambda: NOW_NS).verify()

    assert result.status is A0VerificationStatus.BOOTSTRAP_UNPROVISIONED
    assert result.approved is None
    assert result.lease is None
    assert source.open_calls == 0
    assert isinstance(result.bootstrap, UnprovisionedA0Bootstrap)


def test_wrong_signature_status_fails_and_closes_lease() -> None:
    lease = _Lease(_envelope())
    result = FixedA0Verifier(
        _Source(lease),
        _Bootstrap(BootstrapStatus.REJECTED),
        lambda: NOW_NS,
    ).verify()

    assert result.status is A0VerificationStatus.INVALID
    assert result.approved is None
    assert result.lease is None
    assert lease.close_calls == 1


def test_expired_envelope_is_distinct_and_never_calls_bootstrap() -> None:
    lease = _Lease(_envelope())
    bootstrap = _Bootstrap()

    result = FixedA0Verifier(
        _Source(lease), bootstrap, lambda: NOW_NS + 900_000_000_001
    ).verify()

    assert result.status is A0VerificationStatus.EXPIRED
    assert bootstrap.calls == []
    assert lease.close_calls == 1


def test_future_issued_or_non_exact_interval_is_invalid() -> None:
    for payload in (
        _envelope(
            body_update={
                "issued_unix_ns": NOW_NS + 1,
                "expires_unix_ns": NOW_NS + 900_000_000_001,
            }
        ),
        _envelope(body_update={"expires_unix_ns": NOW_NS + 900_000_000_001}),
    ):
        result = FixedA0Verifier(
            _Source(_Lease(payload)), _Bootstrap(), lambda: NOW_NS
        ).verify()
        assert result.status is A0VerificationStatus.INVALID


def test_extra_field_wrong_scope_and_noncanonical_payload_are_invalid() -> None:
    decoded = json.loads(_envelope())
    extra = dict(decoded)
    extra["unexpected"] = False
    noncanonical = json.dumps(decoded, sort_keys=False).encode()
    cases = (
        _canonical(extra),
        _envelope(body_update={"retry_authorized": True}),
        noncanonical,
    )
    for payload in cases:
        lease = _Lease(payload)
        result = FixedA0Verifier(
            _Source(lease), _Bootstrap(), lambda: NOW_NS
        ).verify()
        assert result.status is A0VerificationStatus.INVALID
        assert lease.close_calls == 1


def test_duplicate_json_key_is_invalid() -> None:
    payload = _envelope()
    duplicate = payload.replace(
        b'{"body":',
        b'{"schema_version":1,"body":',
        1,
    )
    lease = _Lease(duplicate)

    result = FixedA0Verifier(_Source(lease), _Bootstrap(), lambda: NOW_NS).verify()

    assert result.status is A0VerificationStatus.INVALID
    assert lease.close_calls == 1


def test_invalid_lease_or_cleanup_failure_is_fail_closed() -> None:
    invalid = _Lease(_envelope(), valid=False)
    result = FixedA0Verifier(_Source(invalid), _Bootstrap(), lambda: NOW_NS).verify()
    assert result.status is A0VerificationStatus.INVALID

    cleanup = _Lease(_envelope(), valid=False)
    cleanup.close = lambda: False  # type: ignore[method-assign]
    result = FixedA0Verifier(_Source(cleanup), _Bootstrap(), lambda: NOW_NS).verify()
    assert result.status is A0VerificationStatus.CLEANUP_FAILED


def test_read_failure_after_open_closes_the_approval_lease_exactly_once() -> None:
    lease = _Lease(_envelope())

    def fail_read() -> bytes:
        raise OSError("simulated read failure")

    lease.read_exact = fail_read  # type: ignore[method-assign]

    result = FixedA0Verifier(_Source(lease), _Bootstrap(), lambda: NOW_NS).verify()

    assert result.status is A0VerificationStatus.INVALID
    assert result.lease is None
    assert lease.close_calls == 1


def test_approved_triple_is_frozen() -> None:
    result = FixedA0Verifier(
        _Source(_Lease(_envelope())), _Bootstrap(), lambda: NOW_NS
    ).verify()
    assert result.approved is not None

    try:
        replace(result.approved, static_bindings_digest="f" * 64)
    except Exception as error:  # pragma: no cover - dataclasses.replace is valid here
        raise AssertionError("replace should return a distinct frozen value") from error
    assert result.approved.static_bindings_digest == DIGEST_A
