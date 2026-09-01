from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[2]
AUDIT_JSON = ROOT / "docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.json"
AUDIT_MARKDOWN = ROOT / "docs/ai/M2_S3A_PACKAGE_GAP_AUDIT.md"
STATUS = (
    "M2_S3A_CURRENT_SOURCE_PACKAGE_GAP_AUDITED_"
    "REBUILD_NOT_STARTED_NO_RELEASE_AUTHORITY"
)
EXPECTED_GAPS = [
    (
        "GAP-01_CURRENT_PYTHON_RUNTIME_INCLUSION_NOT_DEMONSTRATED",
        "M2-S3B",
    ),
    ("GAP-02_CURRENT_FRONTEND_ASSETS_NOT_PACKAGED", "M2-S3B"),
    ("GAP-03_PACKAGED_M2SYNTHETIC_RUNTIME_SMOKE_ABSENT", "M2-S3C"),
    ("GAP-04_PACKAGED_S2D_EXPORT_ROUND_TRIP_ABSENT", "M2-S3D"),
    ("GAP-05_PACKAGED_S2E_REPRODUCTION_EVIDENCE_ABSENT", "M2-S3D"),
    (
        "GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT",
        "M2-S3F",
    ),
    ("GAP-07_PACKAGE_README_SYNTHETIC_BOUNDARY_STALE", "M2-S3B"),
    (
        "GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT",
        "M2-S3E_OR_EXTERNAL_CLEAN_ENVIRONMENT",
    ),
]
EXPECTED_HASHES = {
    "canonical_proposal": (
        "docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx",
        "2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5",
    ),
    "pyinstaller_spec": (
        "packaging/PDU-Exam-Observer.spec",
        "1ed8a4a36560c3c48b5fa10d505322366d28999caa262644b7e872d6f35e0286",
    ),
    "release_builder": (
        "scripts/build_release.ps1",
        "369a621311faf32c5201299925b30b12cb158725aac4bc4a9d1b0e25bd575ef2",
    ),
    "release_smoke": (
        "scripts/smoke_release.ps1",
        "c057c7004538ea9b2abb0a630848e3911b5dd4bd5441c07a044d50e8c3932502",
    ),
    "m1_release_smoke": (
        "scripts/smoke_m1_release.ps1",
        "4bd904a65e611ffa9e682c1c64b680ac1a38b5e661ac65da18c40f8fa66d6753",
    ),
    "package_readme": (
        "packaging/README.txt",
        "bb5d18a6173d3beced8f8a6ec4aa7e38adf4385f705fba469b4b451e7cfb6e0f",
    ),
    "historical_pyz_inventory": (
        "packaging/build/PDU-Exam-Observer/PYZ-00.toc",
        "57af434ec476abbbbfdb8a1a8c725fbc49fa499290cdb913e0bafd4b31e643c1",
    ),
    "current_observed_frontend_dist": (
        "apps/web/dist/assets/index-DB9w6fTP.js",
        "aa135499fe6eb29199dbedc0254f8b7aca6568646d7c16bd47226ebeb76fccf5",
    ),
    "packaged_frontend_bundle": (
        "packaging/release/PDU-Exam-Observer/_internal/assets/web/assets/"
        "index-CsHrbwBH.js",
        "bdc4a3564bf765b15ebe25ec6e45f6b9200212ccae2b6d84932a0b3a363c3d36",
    ),
    "historical_executable": (
        "packaging/release/PDU-Exam-Observer/PDUExamObserver.exe",
        "ec0d26a9f63ae3ec56ef1a2ac75235df5e419884697d86c1db37100604dfd7ff",
    ),
    "bundled_release_manifest": (
        "packaging/release/PDU-Exam-Observer/RELEASE_MANIFEST.json",
        "9c4dde09bce5833ceaac4eb863171ba0b524368c329d6254e4c360d10d77c256",
    ),
    "detached_release_manifest": (
        "packaging/RELEASE_MANIFEST.json",
        "9c4dde09bce5833ceaac4eb863171ba0b524368c329d6254e4c360d10d77c256",
    ),
}
EXPECTED_AUTHORITY = {
    "authority_status": "AUTHORITY_NOT_ISSUED",
    "clean_machine_verified": False,
    "collection_authorized": False,
    "d1_go": False,
    "device_gate_decision": "UNVERIFIED",
    "distribution_ready": False,
    "execution_authorized": False,
    "package_contains_integration": False,
    "package_rebuild_started": False,
    "participant_collection_authorized": False,
    "physical_camera_access_authorized": False,
    "production_reconciler_implemented": False,
    "production_reconciler_real_storage_verified": False,
    "real_data_deletion_authorized": False,
    "release_authorized": False,
    "research_ready": False,
    "same_host_portable_verified": False,
}


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_audit() -> dict[str, Any]:
    raw = AUDIT_JSON.read_bytes()
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    document = json.loads(raw, object_pairs_hook=_reject_duplicates)
    assert isinstance(document, dict)
    return document


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_json_is_canonical_closed_and_body_hash_bound() -> None:
    document = _read_audit()

    assert set(document) == {
        "artifact_kind",
        "body",
        "body_sha256",
        "schema_version",
        "status",
    }
    assert document["artifact_kind"] == "M2_S3A_PACKAGE_GAP_AUDIT"
    assert document["schema_version"] == 1
    assert document["status"] == STATUS
    assert set(document["body"]) == {
        "audit_result",
        "authority_ceiling",
        "gap_matrix",
        "historical_package",
        "next_task",
        "observed_on",
        "prohibited_claims",
        "source_revision",
    }
    assert document["body_sha256"] == hashlib.sha256(
        _canonical(document["body"])
    ).hexdigest()
    assert AUDIT_JSON.read_bytes() == _canonical(document) + b"\n"


def test_audit_pins_current_source_and_historical_package_bytes() -> None:
    document = _read_audit()
    body = document["body"]
    source = body["source_revision"]
    package = body["historical_package"]

    assert source["git"] == {
        "branch": "main",
        "head": "7912bd9",
        "worktree_state": "DIRTY_TASK_SCOPED",
    }
    assert source["rp2"] == {
        "binding_schema_exact_bytes_sha256": (
            "abc494b96a3cc52eda57c43d677c83245736ab65ff923faa4e39524cf84f2dc5"
        ),
        "candidate_exact_bytes_sha256": (
            "15f3bcc27411b1534e6214d8818af70cf46076776af4ae73551d508d0f0f7119"
        ),
        "static_bindings_digest": (
            "38a17dcc4ea214a2d52ef2bb825e502bcf88d7dbf48ebc2f3758da93b6d2a585"
        ),
    }
    assert source["immutable_inputs"] == {
        key: {"path": path, "sha256": digest}
        for key, (path, digest) in EXPECTED_HASHES.items()
    }
    for path, digest in EXPECTED_HASHES.values():
        assert _sha256(ROOT / path) == digest

    bundled = ROOT / EXPECTED_HASHES["bundled_release_manifest"][0]
    detached = ROOT / EXPECTED_HASHES["detached_release_manifest"][0]
    assert bundled.read_bytes() == detached.read_bytes()
    manifest = json.loads(bundled.read_text(encoding="utf-8"))
    assert package == {
        "integrity_status": "MANIFEST_VERIFIED",
        "manifest_entry_count": len(manifest["files"]),
        "package_rebuilt": False,
        "product_version": manifest["product_version"],
        "python_inclusion_evidence": "AUXILIARY_BUILD_TOC_ONLY",
        "python_synthetic_build_toc_match_count": 0,
        "source_currency": "HISTORICAL_NOT_CURRENT_SOURCE",
        "source_revision": manifest["source_revision"],
        "test_receipt_count": len(manifest["test_receipts"]),
    }


def test_audit_has_exact_open_gap_matrix_and_historical_current_separation() -> None:
    body = _read_audit()["body"]
    gaps = body["gap_matrix"]

    assert [(gap["gap_id"], gap["closure_task"]) for gap in gaps] == EXPECTED_GAPS
    assert all(gap["status"] == "OPEN" for gap in gaps)
    assert all(gap["authority_effect"] == "NONE" for gap in gaps)
    assert {gap["evidence_classification"] for gap in gaps} <= {
        "OBSERVED",
        "SOURCE_VERIFIED",
        "UNVERIFIED",
    }
    assert body["audit_result"] == "PACKAGE_GAP_CONFIRMED"
    assert body["next_task"] == "M2_S3B_DETERMINISTIC_PACKAGE_INTEGRATION"

    current_frontend = (ROOT / EXPECTED_HASHES["current_observed_frontend_dist"][0]).read_text(
        encoding="utf-8"
    )
    packaged_frontend = (ROOT / EXPECTED_HASHES["packaged_frontend_bundle"][0]).read_text(
        encoding="utf-8"
    )
    pyz_inventory = (ROOT / EXPECTED_HASHES["historical_pyz_inventory"][0]).read_text(
        encoding="utf-8"
    )
    assert "NOMINAL_20M" in current_frontend
    assert "/synthetic-runs" in current_frontend
    assert "NOMINAL_20M" not in packaged_frontend
    assert "/synthetic-runs" not in packaged_frontend
    assert "m2_synthetic" not in pyz_inventory


def test_audit_markdown_mirrors_receipt_without_release_claim() -> None:
    document = _read_audit()
    markdown = AUDIT_MARKDOWN.read_text(encoding="utf-8")

    assert STATUS in markdown
    assert document["body_sha256"] in markdown
    for gap_id, closure_task in EXPECTED_GAPS:
        assert gap_id in markdown
        assert closure_task in markdown
    for _path, digest in EXPECTED_HASHES.values():
        assert digest in markdown
    for label in ("OBSERVED", "SOURCE_VERIFIED", "DERIVED", "UNVERIFIED"):
        assert label in markdown
    assert "HISTORICAL_NOT_CURRENT_SOURCE" in markdown
    assert "AUXILIARY_BUILD_TOC_ONLY" in markdown
    for prohibited in document["body"]["prohibited_claims"]:
        assert f"`{prohibited}` is prohibited" in markdown


def test_audit_keeps_full_authority_ceiling_and_package_inputs_immutable() -> None:
    body = _read_audit()["body"]

    assert body["authority_ceiling"] == EXPECTED_AUTHORITY
    assert body["prohibited_claims"] == [
        "CLEAN_MACHINE_VERIFIED",
        "CURRENT_SOURCE_PACKAGE_VERIFIED",
        "DISTRIBUTION_READY",
        "RELEASE_AUTHORIZED",
    ]
    for path, digest in EXPECTED_HASHES.values():
        assert _sha256(ROOT / path) == digest

