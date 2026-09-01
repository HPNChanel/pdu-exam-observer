"""Offline verifier for one M2-S2D synthetic evidence bundle."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdu_exam_observer.m2_synthetic_evidence import (  # noqa: E402
    MAX_EVIDENCE_BYTES,
    canonical_json_bytes,
    verify_synthetic_evidence_bytes,
)


def _read_input(arguments: list[str]) -> bytes:
    if len(arguments) != 1:
        return b""
    path = Path(arguments[0])
    try:
        metadata = path.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)
        ):
            return b""
        if metadata.st_size > MAX_EVIDENCE_BYTES:
            return b" " * (MAX_EVIDENCE_BYTES + 1)
        payload = path.read_bytes()
        after = path.lstat()
        if (
            (metadata.st_dev, metadata.st_ino, metadata.st_size)
            != (after.st_dev, after.st_ino, after.st_size)
            or len(payload) != metadata.st_size
        ):
            return b""
        return payload
    except OSError:
        return b""


def main(arguments: list[str] | None = None) -> int:
    try:
        receipt = verify_synthetic_evidence_bytes(
            _read_input(list(sys.argv[1:] if arguments is None else arguments))
        )
    except Exception:
        receipt = verify_synthetic_evidence_bytes(b"")
    sys.stdout.buffer.write(canonical_json_bytes(receipt.as_dict()))
    return 0 if receipt.result == "EVIDENCE_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
