from __future__ import annotations

import io
import zipfile

import pytest

from pdu_exam_observer.showcase.export_contract import (
    build_research_export,
    validate_research_export,
)


def _record() -> dict[str, object]:
    return {
        "export_id": "",
        "manifest_sha256": "",
        "schema_version": 1,
        "record_count": 0,
        "sample_id": "sample-1",
        "participant_pseudonym": "P03",
        "session_pseudonym": "P03-S1",
        "source_kind": "REAL",
        "parent_provenance_id": None,
        "pose": {"topology": "mediapipe-33", "pose_count": 0, "landmarks": []},
        "label": "UNCERTAIN",
        "quality": {},
        "focus": {},
        "timing": {"captured_ns": 1, "offset_ms": 0, "phase": "CONFIRMATORY"},
    }


def test_export_encoder_binds_canonical_record_bytes_and_exact_envelope() -> None:
    payload, manifest = build_research_export((_record(),), export_id="export-1")

    validated = validate_research_export(payload)

    assert validated.manifest == manifest
    assert validated.records[0]["export_id"] == "export-1"
    assert validated.records[0]["manifest_sha256"] == manifest["manifest_sha256"]
    assert set(manifest) == {
        "schema_version",
        "export_id",
        "record_count",
        "manifest_sha256",
    }


def test_record_tampering_is_rejected_even_when_manifest_is_unchanged() -> None:
    payload, _ = build_research_export((_record(),), export_id="export-1")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        manifest = archive.read("manifest.json")
        records = archive.read("records.jsonl").replace(b"UNCERTAIN", b"NORMAL   ")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", manifest)
        archive.writestr("records.jsonl", records)

    with pytest.raises(ValueError, match="manifest digest"):
        validate_research_export(output.getvalue())


def test_real_record_requires_phase_inside_allowlisted_timing_object() -> None:
    record = _record()
    record["timing"] = {"captured_ns": 1, "offset_ms": 0}

    with pytest.raises(ValueError, match="phase"):
        build_research_export((record,), export_id="export-1")
