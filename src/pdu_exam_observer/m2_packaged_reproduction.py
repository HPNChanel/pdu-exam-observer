"""Closed stdin protocol for packaged synthetic evidence reproduction."""

from __future__ import annotations

import sys
from enum import StrEnum
from typing import BinaryIO

from pdu_exam_observer.m2_synthetic_evidence import MAX_EVIDENCE_BYTES, canonical_json_bytes
from pdu_exam_observer.m2_synthetic_reproduction import (
    ReproductionClassification,
    reproduce_synthetic_evidence_bytes,
)


class PackagedReproductionFailureCode(StrEnum):
    REQUEST_INVALID = "REQUEST_INVALID"
    INPUT_READ_FAILED = "INPUT_READ_FAILED"
    UNEXPECTED_FAILURE = "UNEXPECTED_FAILURE"


def _protocol_failure(code: PackagedReproductionFailureCode) -> dict[str, object]:
    return {
        "artifact_kind": "M2_PACKAGED_SYNTHETIC_REPRODUCTION_PROTOCOL_FAILURE",
        "classification": "REPRODUCTION_FAILED",
        "failure_code": code.value,
        "status": "M2_S2E_SYNTHETIC_EVIDENCE_REPRODUCTION_NOT_VERIFIED",
    }


def execute_packaged_reproduction(payload: bytes) -> dict[str, object]:
    """Reproduce one in-memory S2D bundle without accepting a filesystem path."""

    try:
        return reproduce_synthetic_evidence_bytes(payload).as_dict()
    except Exception:
        return reproduce_synthetic_evidence_bytes(b"").as_dict()


def main(
    arguments: list[str] | None = None,
    *,
    input_stream: BinaryIO | None = None,
    output_stream: BinaryIO | None = None,
) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    source = sys.stdin.buffer if input_stream is None else input_stream
    target = sys.stdout.buffer if output_stream is None else output_stream
    if args:
        target.write(canonical_json_bytes(_protocol_failure(PackagedReproductionFailureCode.REQUEST_INVALID)))
        return 2
    try:
        payload = source.read(MAX_EVIDENCE_BYTES + 1)
    except Exception:
        target.write(canonical_json_bytes(_protocol_failure(PackagedReproductionFailureCode.INPUT_READ_FAILED)))
        return 2
    receipt = execute_packaged_reproduction(payload)
    target.write(canonical_json_bytes(receipt))
    return (
        0
        if receipt.get("classification")
        == ReproductionClassification.EXACTLY_REPRODUCED.value
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
