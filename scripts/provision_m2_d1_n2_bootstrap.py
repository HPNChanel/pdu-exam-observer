"""Separately authorized one-shot D1-N2 bootstrap provisioning entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pdu_exam_observer.m2_d1_n2_bootstrap import ProvisioningResult
from pdu_exam_observer.m2_d1_n2_bootstrap_install import (
    create_production_bootstrap_installer,
    parse_operator_authority,
)

_MAX_BOOTSTRAP_BYTES = 16_384


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Install one externally approved public D1-N2 bootstrap bundle. "
            "Source availability is not execution authority."
        )
    )
    parser.add_argument("--bundle-file", type=Path, required=True)
    parser.add_argument("--authority-revision", required=True)
    parser.add_argument("--bootstrap-bundle-sha256", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--bootstrap-epoch-digest", required=True)
    parser.add_argument("--one-shot", choices=("true",), required=True)
    parser.add_argument("--overwrite", choices=("false",), required=True)
    return parser


def _emit(result: ProvisioningResult, receipt_sha256: str | None = None) -> None:
    payload: dict[str, object] = {
        "authority_issued": False,
        "physical_camera_access_authorized": False,
        "result": result.value,
        "schema_version": 1,
    }
    if receipt_sha256 is not None:
        payload["provisioning_receipt_sha256"] = receipt_sha256
    print(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    )


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    authority = parse_operator_authority(
        authority_revision=arguments.authority_revision,
        bootstrap_bundle_sha256=arguments.bootstrap_bundle_sha256,
        key_id=arguments.key_id,
        bootstrap_epoch_digest=arguments.bootstrap_epoch_digest,
        one_shot=arguments.one_shot,
        overwrite=arguments.overwrite,
    )
    if authority is None:
        _emit(ProvisioningResult.INVALID_INPUT)
        return 2
    try:
        bundle = arguments.bundle_file.read_bytes()
    except OSError:
        _emit(ProvisioningResult.INVALID_INPUT)
        return 2
    if not 0 < len(bundle) <= _MAX_BOOTSTRAP_BYTES:
        _emit(ProvisioningResult.INVALID_INPUT)
        return 2

    installer = create_production_bootstrap_installer()
    if installer is None:
        _emit(ProvisioningResult.PLATFORM_UNSUPPORTED)
        return 2
    outcome = installer.install(bundle, authority)
    receipt_digest = (
        hashlib.sha256(outcome.receipt.canonical_bytes()).hexdigest()
        if outcome.receipt is not None
        else None
    )
    _emit(outcome.result, receipt_digest)
    return 0 if outcome.result is ProvisioningResult.INSTALLED else 2


if __name__ == "__main__":
    raise SystemExit(main())
