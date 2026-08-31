from __future__ import annotations

import base64
import hashlib
import json
import struct
from dataclasses import replace

import pytest

from pdu_exam_observer.m2_d1_n2_bootstrap import (
    BOOTSTRAP_EPOCH_CANONICAL_BYTES,
    BOOTSTRAP_EPOCH_DIGEST,
    BOOTSTRAP_EPOCH_PREIMAGE,
    BootstrapInstallAuthority,
    ProvisioningReceiptV1,
    ProvisioningResult,
    parse_bootstrap_bundle,
    parse_provisioning_receipt,
    verify_approved_bootstrap_bundle,
)

PUBLIC_BLOB = struct.pack("<II", 0x31534345, 32) + bytes(range(1, 65))
KEY_ID = hashlib.sha256(PUBLIC_BLOB).hexdigest()
EPOCH_DIGEST = BOOTSTRAP_EPOCH_DIGEST
ALTERNATE_EPOCH_DIGEST = "cd" * 32
SIGNATURE = bytes(range(64))

EXPECTED_EPOCH_CANONICAL_BYTES = (
    b'{"authority_revision":"d1-n2-authority-v1",'
    b'"bootstrap_bundle_creation":"ONE_SHOT_CREATE_NEW",'
    b'"custody_profile":"WINDOWS_CNG_USER_NONEXPORTABLE_OFFLINE_V1",'
    b'"domain":"D1N2/A0_BOOTSTRAP_EPOCH/v1","key_algorithm":"ECDSA_P256",'
    b'"key_creation":"CREATE_ONLY","key_export_policy":"NONE",'
    b'"key_name":"PDUExamObserver.D1N2.A0Signing.v1",'
    b'"key_storage_provider":"Microsoft Software Key Storage Provider",'
    b'"key_storage_scope":"CURRENT_USER","private_key_backup":"PROHIBITED",'
    b'"public_key_format":"BCRYPT_ECCPUBLIC_BLOB_P256","schema_version":1,'
    b'"signature_algorithm":"ECDSA_P256_SHA256_IEEE_P1363",'
    b'"target_workstation_private_key":"PROHIBITED"}'
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _bundle(
    *,
    root_update: dict[str, object] | None = None,
    body_update: dict[str, object] | None = None,
) -> bytes:
    body = {
        "authority_revision": "d1-n2-authority-v1",
        "bootstrap_epoch_digest": EPOCH_DIGEST,
        "public_key_b64url": base64.urlsafe_b64encode(PUBLIC_BLOB)
        .rstrip(b"=")
        .decode("ascii"),
        "public_key_format": "BCRYPT_ECCPUBLIC_BLOB_P256",
    }
    if body_update:
        body.update(body_update)
    root = {
        "body": body,
        "domain": "D1N2/A0_BOOTSTRAP/v1",
        "key_id": KEY_ID,
        "schema_version": 1,
        "signature_algorithm": "ECDSA_P256_SHA256_IEEE_P1363",
        "signature_b64url": base64.urlsafe_b64encode(SIGNATURE)
        .rstrip(b"=")
        .decode("ascii"),
    }
    if root_update:
        root.update(root_update)
    return _canonical(root)


def _receipt() -> ProvisioningReceiptV1:
    return ProvisioningReceiptV1(
        result=ProvisioningResult.INSTALLED,
        installed_unix_ns=123,
        bootstrap_bundle_sha256=hashlib.sha256(_bundle()).hexdigest(),
        key_id=KEY_ID,
        bootstrap_epoch_digest=EPOCH_DIGEST,
        create_new=True,
        no_reparse=True,
        share_zero=True,
        write_flushed=True,
        parent_durable=True,
        promoted_no_replace=True,
        readback_verified=True,
        leaf_identity_digest="12" * 32,
        parent_identity_digest="34" * 32,
        cleanup_clean=True,
    )


def test_bootstrap_epoch_preimage_is_exact_and_immutable() -> None:
    assert type(BOOTSTRAP_EPOCH_PREIMAGE) is tuple
    assert all(type(pair) is tuple and len(pair) == 2 for pair in BOOTSTRAP_EPOCH_PREIMAGE)
    assert BOOTSTRAP_EPOCH_CANONICAL_BYTES == EXPECTED_EPOCH_CANONICAL_BYTES
    assert len(BOOTSTRAP_EPOCH_CANONICAL_BYTES) == 626
    assert (
        hashlib.sha256(BOOTSTRAP_EPOCH_CANONICAL_BYTES).hexdigest()
        == "736a6760f7d8f0f635c0d1e9b626fe38d60a1c36f7c10131929a4a588597659b"
        == BOOTSTRAP_EPOCH_DIGEST
    )


def test_parse_bootstrap_bundle_accepts_exact_canonical_public_p256_envelope() -> None:
    parsed = parse_bootstrap_bundle(_bundle())

    assert parsed is not None
    assert parsed.canonical_bytes == _bundle()
    assert parsed.public_key_blob == PUBLIC_BLOB
    assert parsed.key_id == KEY_ID
    assert parsed.bootstrap_epoch_digest == EPOCH_DIGEST
    assert parsed.signature == SIGNATURE
    assert parsed.canonical_body == _canonical(
        {
            "authority_revision": "d1-n2-authority-v1",
            "bootstrap_epoch_digest": EPOCH_DIGEST,
            "public_key_b64url": base64.urlsafe_b64encode(PUBLIC_BLOB)
            .rstrip(b"=")
            .decode("ascii"),
            "public_key_format": "BCRYPT_ECCPUBLIC_BLOB_P256",
        }
    )


@pytest.mark.parametrize(
    "payload",
    [
        _bundle(root_update={"extra": False}),
        _bundle(body_update={"extra": False}),
        _bundle(root_update={"schema_version": True}),
        _bundle(root_update={"signature_b64url": "AA=="}),
        _bundle(body_update={"bootstrap_epoch_digest": "AB" * 32}),
        _bundle(
            body_update={
                "public_key_b64url": base64.urlsafe_b64encode(
                    struct.pack("<II", 0x32534345, 32) + bytes(range(1, 65))
                )
                .rstrip(b"=")
                .decode("ascii")
            }
        ),
        _bundle() + b"\n",
    ],
)
def test_parse_bootstrap_bundle_rejects_open_or_noncanonical_inputs(
    payload: bytes,
) -> None:
    assert parse_bootstrap_bundle(payload) is None


def test_parse_bootstrap_bundle_rejects_duplicate_json_keys() -> None:
    duplicate = _bundle().replace(b'"domain":', b'"domain":"duplicate","domain":', 1)

    assert parse_bootstrap_bundle(duplicate) is None


def test_parse_bootstrap_bundle_rejects_another_well_formed_epoch_digest() -> None:
    payload = _bundle(
        body_update={"bootstrap_epoch_digest": ALTERNATE_EPOCH_DIGEST}
    )

    assert parse_bootstrap_bundle(payload) is None


def test_install_authority_rejects_matching_alternate_epoch_objects() -> None:
    parsed = parse_bootstrap_bundle(_bundle())
    assert parsed is not None
    alternate_bundle = replace(
        parsed,
        bootstrap_epoch_digest=ALTERNATE_EPOCH_DIGEST,
    )
    authority = BootstrapInstallAuthority(
        authority_revision="d1-n2-authority-v1",
        bootstrap_bundle_sha256=hashlib.sha256(parsed.canonical_bytes).hexdigest(),
        key_id=KEY_ID,
        bootstrap_epoch_digest=ALTERNATE_EPOCH_DIGEST,
        one_shot=True,
        overwrite=False,
    )

    assert authority.valid_for(alternate_bundle) is False


def test_external_approval_and_self_signature_are_both_required() -> None:
    authority = BootstrapInstallAuthority(
        authority_revision="d1-n2-authority-v1",
        bootstrap_bundle_sha256=hashlib.sha256(_bundle()).hexdigest(),
        key_id=KEY_ID,
        bootstrap_epoch_digest=EPOCH_DIGEST,
        one_shot=True,
        overwrite=False,
    )
    calls: list[tuple[bytes, bytes, bytes]] = []

    def accept(public_blob: bytes, message: bytes, signature: bytes) -> bool:
        calls.append((public_blob, message, signature))
        return True

    approved = verify_approved_bootstrap_bundle(_bundle(), authority, accept)

    assert approved is not None
    assert calls == [(PUBLIC_BLOB, approved.canonical_body, SIGNATURE)]
    assert (
        verify_approved_bootstrap_bundle(
            _bundle(),
            BootstrapInstallAuthority(
                authority_revision="d1-n2-authority-v1",
                bootstrap_bundle_sha256="cd" * 32,
                key_id=KEY_ID,
                bootstrap_epoch_digest=EPOCH_DIGEST,
                one_shot=True,
                overwrite=False,
            ),
            accept,
        )
        is None
    )
    assert verify_approved_bootstrap_bundle(_bundle(), authority, lambda *_: False) is None


def test_provisioning_receipt_round_trips_only_closed_sanitized_fields() -> None:
    receipt = _receipt()

    encoded = receipt.canonical_bytes()

    assert parse_provisioning_receipt(encoded) == receipt
    assert json.loads(encoded)["ceremony_revision"] == "d1-n2-b0-r1-provisioning-v1"
    assert b"username" not in encoded
    assert b"path" not in encoded
    assert parse_provisioning_receipt(encoded + b"\n") is None


def test_provisioning_receipt_rejects_another_well_formed_epoch_digest() -> None:
    receipt = replace(
        _receipt(),
        bootstrap_epoch_digest=ALTERNATE_EPOCH_DIGEST,
    )

    assert receipt.valid() is False
    with pytest.raises(ValueError, match="invalid provisioning receipt"):
        receipt.canonical_bytes()
