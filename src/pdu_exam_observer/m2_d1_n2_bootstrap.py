"""Closed, non-authorizing D1-N2 bootstrap and provisioning contracts."""

from __future__ import annotations

import base64
import hashlib
import json
import struct
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

BOOTSTRAP_DOMAIN = "D1N2/A0_BOOTSTRAP/v1"
BOOTSTRAP_AUTHORITY_REVISION = "d1-n2-authority-v1"
BOOTSTRAP_SIGNATURE_ALGORITHM = "ECDSA_P256_SHA256_IEEE_P1363"
BOOTSTRAP_PUBLIC_KEY_FORMAT = "BCRYPT_ECCPUBLIC_BLOB_P256"
PROVISIONING_RECEIPT_DOMAIN = "D1N2/A0_BOOTSTRAP_PROVISIONING_RECEIPT/v1"
PROVISIONING_CEREMONY_REVISION = "d1-n2-b0-r1-provisioning-v1"
_BCRYPT_ECDSA_PUBLIC_P256_MAGIC = 0x31534345
_P256_COORDINATE_BYTES = 32
_PUBLIC_BLOB_BYTES = 8 + 2 * _P256_COORDINATE_BYTES
_ROOT_KEYS = {
    "body",
    "domain",
    "key_id",
    "schema_version",
    "signature_algorithm",
    "signature_b64url",
}
_BODY_KEYS = {
    "authority_revision",
    "bootstrap_epoch_digest",
    "public_key_b64url",
    "public_key_format",
}
_RECEIPT_KEYS = {
    "bootstrap_bundle_sha256",
    "bootstrap_epoch_digest",
    "ceremony_revision",
    "cleanup_clean",
    "create_new",
    "domain",
    "installed_unix_ns",
    "key_id",
    "leaf_identity_digest",
    "no_reparse",
    "parent_durable",
    "parent_identity_digest",
    "promoted_no_replace",
    "readback_verified",
    "result",
    "schema_version",
    "share_zero",
    "write_flushed",
}


@dataclass(frozen=True, slots=True)
class ParsedBootstrapBundle:
    canonical_bytes: bytes
    canonical_body: bytes
    public_key_blob: bytes
    key_id: str
    bootstrap_epoch_digest: str
    signature: bytes


@dataclass(frozen=True, slots=True)
class BootstrapInstallAuthority:
    authority_revision: str
    bootstrap_bundle_sha256: str
    key_id: str
    bootstrap_epoch_digest: str
    one_shot: bool
    overwrite: bool

    def valid_for(self, bundle: ParsedBootstrapBundle) -> bool:
        return (
            self.authority_revision == BOOTSTRAP_AUTHORITY_REVISION
            and _is_digest(self.bootstrap_bundle_sha256)
            and self.bootstrap_bundle_sha256
            == hashlib.sha256(bundle.canonical_bytes).hexdigest()
            and self.key_id == bundle.key_id
            and self.bootstrap_epoch_digest == BOOTSTRAP_EPOCH_DIGEST
            and bundle.bootstrap_epoch_digest == BOOTSTRAP_EPOCH_DIGEST
            and self.bootstrap_epoch_digest == bundle.bootstrap_epoch_digest
            and type(self.one_shot) is bool
            and self.one_shot
            and type(self.overwrite) is bool
            and not self.overwrite
        )


class ProvisioningResult(StrEnum):
    INSTALLED = "INSTALLED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    INVALID_INPUT = "INVALID_INPUT"
    PLATFORM_UNSUPPORTED = "PLATFORM_UNSUPPORTED"
    WRITE_FAILED = "WRITE_FAILED"
    DURABILITY_FAILED = "DURABILITY_FAILED"
    READBACK_FAILED = "READBACK_FAILED"
    CLEANUP_FAILED = "CLEANUP_FAILED"


@dataclass(frozen=True, slots=True)
class ProvisioningReceiptV1:
    result: ProvisioningResult
    installed_unix_ns: int
    bootstrap_bundle_sha256: str
    key_id: str
    bootstrap_epoch_digest: str
    create_new: bool
    no_reparse: bool
    share_zero: bool
    write_flushed: bool
    parent_durable: bool
    promoted_no_replace: bool
    readback_verified: bool
    leaf_identity_digest: str
    parent_identity_digest: str
    cleanup_clean: bool

    def valid(self) -> bool:
        booleans = (
            self.create_new,
            self.no_reparse,
            self.share_zero,
            self.write_flushed,
            self.parent_durable,
            self.promoted_no_replace,
            self.readback_verified,
            self.cleanup_clean,
        )
        return (
            type(self.result) is ProvisioningResult
            and type(self.installed_unix_ns) is int
            and 0 <= self.installed_unix_ns < 1 << 63
            and all(
                _is_digest(value)
                for value in (
                    self.bootstrap_bundle_sha256,
                    self.key_id,
                    self.bootstrap_epoch_digest,
                    self.leaf_identity_digest,
                    self.parent_identity_digest,
                )
            )
            and all(type(value) is bool for value in booleans)
            and self.bootstrap_epoch_digest == BOOTSTRAP_EPOCH_DIGEST
            and (
                self.result is not ProvisioningResult.INSTALLED or all(booleans)
            )
        )

    def canonical_bytes(self) -> bytes:
        if not self.valid():
            raise ValueError("invalid provisioning receipt")
        return _canonical_bytes(
            {
                "bootstrap_bundle_sha256": self.bootstrap_bundle_sha256,
                "bootstrap_epoch_digest": self.bootstrap_epoch_digest,
                "ceremony_revision": PROVISIONING_CEREMONY_REVISION,
                "cleanup_clean": self.cleanup_clean,
                "create_new": self.create_new,
                "domain": PROVISIONING_RECEIPT_DOMAIN,
                "installed_unix_ns": self.installed_unix_ns,
                "key_id": self.key_id,
                "leaf_identity_digest": self.leaf_identity_digest,
                "no_reparse": self.no_reparse,
                "parent_durable": self.parent_durable,
                "parent_identity_digest": self.parent_identity_digest,
                "promoted_no_replace": self.promoted_no_replace,
                "readback_verified": self.readback_verified,
                "result": self.result.value,
                "schema_version": 1,
                "share_zero": self.share_zero,
                "write_flushed": self.write_flushed,
            }
        )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


BOOTSTRAP_EPOCH_PREIMAGE: tuple[tuple[str, object], ...] = (
    ("authority_revision", BOOTSTRAP_AUTHORITY_REVISION),
    ("bootstrap_bundle_creation", "ONE_SHOT_CREATE_NEW"),
    ("custody_profile", "WINDOWS_CNG_USER_NONEXPORTABLE_OFFLINE_V1"),
    ("domain", "D1N2/A0_BOOTSTRAP_EPOCH/v1"),
    ("key_algorithm", "ECDSA_P256"),
    ("key_creation", "CREATE_ONLY"),
    ("key_export_policy", "NONE"),
    ("key_name", "PDUExamObserver.D1N2.A0Signing.v1"),
    ("key_storage_provider", "Microsoft Software Key Storage Provider"),
    ("key_storage_scope", "CURRENT_USER"),
    ("private_key_backup", "PROHIBITED"),
    ("public_key_format", BOOTSTRAP_PUBLIC_KEY_FORMAT),
    ("schema_version", 1),
    ("signature_algorithm", BOOTSTRAP_SIGNATURE_ALGORITHM),
    ("target_workstation_private_key", "PROHIBITED"),
)
BOOTSTRAP_EPOCH_CANONICAL_BYTES = _canonical_bytes(dict(BOOTSTRAP_EPOCH_PREIMAGE))
BOOTSTRAP_EPOCH_DIGEST = hashlib.sha256(BOOTSTRAP_EPOCH_CANONICAL_BYTES).hexdigest()
assert len(BOOTSTRAP_EPOCH_CANONICAL_BYTES) == 626
assert (
    BOOTSTRAP_EPOCH_DIGEST
    == "736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b"
)


def _closed_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _decode_closed(payload: bytes) -> dict[str, object] | None:
    if type(payload) is not bytes:
        return None
    try:
        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_closed_pairs)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    if type(decoded) is not dict:
        return None
    try:
        if _canonical_bytes(decoded) != payload:
            return None
    except (TypeError, ValueError):
        return None
    return decoded


def _is_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _decode_unpadded_b64url(value: object, *, exact_length: int) -> bytes | None:
    if type(value) is not str or not value or "=" in value:
        return None
    try:
        encoded = value.encode("ascii")
        decoded = base64.b64decode(
            encoded + b"=" * ((4 - len(encoded) % 4) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (UnicodeEncodeError, ValueError):
        return None
    if len(decoded) != exact_length:
        return None
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        return None
    return decoded


def _public_p256_blob(value: object) -> bytes | None:
    blob = _decode_unpadded_b64url(value, exact_length=_PUBLIC_BLOB_BYTES)
    if blob is None:
        return None
    magic, coordinate_size = struct.unpack("<II", blob[:8])
    if (
        magic != _BCRYPT_ECDSA_PUBLIC_P256_MAGIC
        or coordinate_size != _P256_COORDINATE_BYTES
    ):
        return None
    return blob


def parse_bootstrap_bundle(payload: bytes) -> ParsedBootstrapBundle | None:
    root = _decode_closed(payload)
    if (
        root is None
        or set(root) != _ROOT_KEYS
        or type(root.get("schema_version")) is not int
        or root.get("schema_version") != 1
        or root.get("domain") != BOOTSTRAP_DOMAIN
        or root.get("signature_algorithm") != BOOTSTRAP_SIGNATURE_ALGORITHM
        or not _is_digest(root.get("key_id"))
        or type(root.get("body")) is not dict
    ):
        return None
    body = root["body"]
    assert isinstance(body, dict)
    if (
        set(body) != _BODY_KEYS
        or body.get("authority_revision") != BOOTSTRAP_AUTHORITY_REVISION
        or body.get("public_key_format") != BOOTSTRAP_PUBLIC_KEY_FORMAT
        or body.get("bootstrap_epoch_digest") != BOOTSTRAP_EPOCH_DIGEST
    ):
        return None
    public_key_blob = _public_p256_blob(body.get("public_key_b64url"))
    signature = _decode_unpadded_b64url(root.get("signature_b64url"), exact_length=64)
    if (
        public_key_blob is None
        or signature is None
        or hashlib.sha256(public_key_blob).hexdigest() != root["key_id"]
    ):
        return None
    return ParsedBootstrapBundle(
        canonical_bytes=payload,
        canonical_body=_canonical_bytes(body),
        public_key_blob=public_key_blob,
        key_id=str(root["key_id"]),
        bootstrap_epoch_digest=str(body["bootstrap_epoch_digest"]),
        signature=signature,
    )


def verify_approved_bootstrap_bundle(
    payload: bytes,
    authority: BootstrapInstallAuthority,
    verify_signature: Callable[[bytes, bytes, bytes], bool],
) -> ParsedBootstrapBundle | None:
    bundle = parse_bootstrap_bundle(payload)
    if bundle is None or not authority.valid_for(bundle):
        return None
    try:
        verified = verify_signature(
            bundle.public_key_blob,
            bundle.canonical_body,
            bundle.signature,
        )
    except BaseException:
        return None
    return bundle if verified is True else None


def parse_provisioning_receipt(payload: bytes) -> ProvisioningReceiptV1 | None:
    root = _decode_closed(payload)
    if (
        root is None
        or set(root) != _RECEIPT_KEYS
        or type(root.get("schema_version")) is not int
        or root.get("schema_version") != 1
        or root.get("domain") != PROVISIONING_RECEIPT_DOMAIN
        or root.get("ceremony_revision") != PROVISIONING_CEREMONY_REVISION
        or type(root.get("result")) is not str
    ):
        return None
    try:
        result = ProvisioningResult(str(root["result"]))
    except ValueError:
        return None
    boolean_fields = (
        "create_new",
        "no_reparse",
        "share_zero",
        "write_flushed",
        "parent_durable",
        "promoted_no_replace",
        "readback_verified",
        "cleanup_clean",
    )
    if any(type(root.get(field)) is not bool for field in boolean_fields):
        return None
    receipt = ProvisioningReceiptV1(
        result=result,
        installed_unix_ns=root.get("installed_unix_ns"),  # type: ignore[arg-type]
        bootstrap_bundle_sha256=root.get("bootstrap_bundle_sha256"),  # type: ignore[arg-type]
        key_id=root.get("key_id"),  # type: ignore[arg-type]
        bootstrap_epoch_digest=root.get("bootstrap_epoch_digest"),  # type: ignore[arg-type]
        create_new=bool(root["create_new"]),
        no_reparse=bool(root["no_reparse"]),
        share_zero=bool(root["share_zero"]),
        write_flushed=bool(root["write_flushed"]),
        parent_durable=bool(root["parent_durable"]),
        promoted_no_replace=bool(root["promoted_no_replace"]),
        readback_verified=bool(root["readback_verified"]),
        leaf_identity_digest=root.get("leaf_identity_digest"),  # type: ignore[arg-type]
        parent_identity_digest=root.get("parent_identity_digest"),  # type: ignore[arg-type]
        cleanup_clean=bool(root["cleanup_clean"]),
    )
    return receipt if receipt.valid() and receipt.canonical_bytes() == payload else None


__all__ = [
    "BOOTSTRAP_AUTHORITY_REVISION",
    "BOOTSTRAP_DOMAIN",
    "BOOTSTRAP_EPOCH_CANONICAL_BYTES",
    "BOOTSTRAP_EPOCH_DIGEST",
    "BOOTSTRAP_EPOCH_PREIMAGE",
    "BOOTSTRAP_PUBLIC_KEY_FORMAT",
    "BOOTSTRAP_SIGNATURE_ALGORITHM",
    "BootstrapInstallAuthority",
    "ParsedBootstrapBundle",
    "ProvisioningReceiptV1",
    "ProvisioningResult",
    "parse_bootstrap_bundle",
    "parse_provisioning_receipt",
    "verify_approved_bootstrap_bundle",
]
