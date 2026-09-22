"""NumPy-free encoding and validation for the allowlisted research export.

The manifest digest is computed over its three basic fields plus canonical
records with the self-referential ``manifest_sha256`` field blank. Final
records then bind that digest without adding fields to the wire manifest.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPORT_FILES = frozenset({"manifest.json", "records.jsonl"})
RECORD_FIELDS = frozenset(
    {
        "export_id",
        "manifest_sha256",
        "schema_version",
        "record_count",
        "sample_id",
        "participant_pseudonym",
        "session_pseudonym",
        "source_kind",
        "parent_provenance_id",
        "pose",
        "label",
        "quality",
        "focus",
        "timing",
    }
)
MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "export_id",
        "record_count",
        "manifest_sha256",
    }
)


@dataclass(frozen=True, slots=True)
class ValidatedResearchExport:
    manifest: dict[str, Any]
    records: tuple[dict[str, Any], ...]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_records(records: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(_canonical(record) + b"\n" for record in records)


def _manifest_preimage(
    *, export_id: str, records: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "export_id": export_id,
        "record_count": len(records),
        "records": [dict(record, manifest_sha256="") for record in records],
    }


def _validate_record(record: Mapping[str, object]) -> None:
    if set(record) != RECORD_FIELDS:
        raise ValueError("record does not match the exact export envelope")
    if record.get("schema_version") != 1:
        raise ValueError("record schema is incompatible")
    for field in ("sample_id", "participant_pseudonym", "session_pseudonym"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise ValueError("record pseudonymous identifier is invalid")
    source_kind = record.get("source_kind")
    if source_kind not in {"REAL", "AI_RENDERED", "AUGMENTED"}:
        raise ValueError("record source_kind is invalid")
    parent = record.get("parent_provenance_id")
    if source_kind == "AUGMENTED" and (not isinstance(parent, str) or not parent):
        raise ValueError("augmented record requires parent provenance")
    timing = record.get("timing")
    if not isinstance(timing, dict):
        raise ValueError("record timing is invalid")
    if source_kind == "REAL" and timing.get("phase") not in {"PILOT", "CONFIRMATORY"}:
        raise ValueError("REAL record timing.phase must be PILOT or CONFIRMATORY")


def build_research_export(
    records: Sequence[Mapping[str, object]], *, export_id: str
) -> tuple[bytes, dict[str, Any]]:
    """Return a deterministic two-file ZIP and its content-bound manifest."""

    if not export_id or len(export_id) > 128:
        raise ValueError("export_id is required")
    if not records:
        raise ValueError("at least one export record is required")
    prepared: list[dict[str, object]] = []
    identifiers: set[str] = set()
    for source in records:
        record = dict(source)
        _validate_record(record)
        sample_id = str(record["sample_id"])
        if sample_id in identifiers:
            raise ValueError("sample_id must be unique")
        identifiers.add(sample_id)
        prepared.append(
            dict(
                record,
                export_id=export_id,
                manifest_sha256="",
                record_count=len(records),
            )
        )
    manifest_sha256 = hashlib.sha256(
        _canonical(_manifest_preimage(export_id=export_id, records=prepared))
    ).hexdigest()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "export_id": export_id,
        "record_count": len(prepared),
        "manifest_sha256": manifest_sha256,
    }
    final_records = [dict(record, manifest_sha256=manifest_sha256) for record in prepared]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in (
            ("manifest.json", _canonical(manifest)),
            ("records.jsonl", _canonical_records(final_records)),
        ):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return output.getvalue(), manifest


def _source_bytes(source: bytes | Path) -> bytes:
    if isinstance(source, bytes):
        data = source
    elif isinstance(source, Path) and source.is_file() and not source.is_symlink():
        data = source.read_bytes()
    else:
        raise ValueError("export must be bytes or a trusted regular Path")
    if len(data) > 512 * 1024 * 1024:
        raise ValueError("export exceeds its size ceiling")
    return data


def validate_research_export(source: bytes | Path) -> ValidatedResearchExport:
    """Validate archive safety, manifest self-hash, record hash, and envelope binding."""

    try:
        with zipfile.ZipFile(io.BytesIO(_source_bytes(source))) as archive:
            entries = tuple(archive.infolist())
            if len(entries) != 2 or {entry.filename for entry in entries} != EXPORT_FILES:
                raise ValueError("export ZIP must use the exact two-file allowlist")
            if any(
                entry.is_dir()
                or entry.filename != Path(entry.filename).name
                or entry.file_size > 500 * 1024 * 1024
                or (entry.file_size and entry.compress_size == 0)
                or (entry.file_size and entry.file_size / entry.compress_size > 200)
                for entry in entries
            ):
                raise ValueError("export ZIP contains an unsafe entry")
            manifest = json.loads(archive.read("manifest.json"))
            records = tuple(
                json.loads(line)
                for line in archive.read("records.jsonl").decode("utf-8").splitlines()
                if line.strip()
            )
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError, KeyError) as error:
        raise ValueError("export ZIP cannot be decoded") from error
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        raise ValueError("export manifest is incompatible")
    if any(not isinstance(record, dict) for record in records):
        raise ValueError("export records must be objects")
    recorded_manifest_sha256 = manifest.get("manifest_sha256")
    if (
        manifest.get("schema_version") != 1
        or not isinstance(recorded_manifest_sha256, str)
        or manifest.get("record_count") != len(records)
    ):
        raise ValueError("export manifest digest/count is invalid")
    identifiers: set[str] = set()
    for record in records:
        _validate_record(record)
        if (
            record.get("export_id") != manifest.get("export_id")
            or record.get("manifest_sha256") != recorded_manifest_sha256
            or record.get("record_count") != len(records)
        ):
            raise ValueError("record is not bound to its export manifest")
        sample_id = str(record["sample_id"])
        if sample_id in identifiers:
            raise ValueError("sample_id must be unique")
        identifiers.add(sample_id)
    expected_manifest_sha256 = hashlib.sha256(
        _canonical(_manifest_preimage(export_id=str(manifest.get("export_id")), records=records))
    ).hexdigest()
    if expected_manifest_sha256 != recorded_manifest_sha256:
        raise ValueError("export manifest digest does not bind the records")
    return ValidatedResearchExport(manifest=manifest, records=records)
