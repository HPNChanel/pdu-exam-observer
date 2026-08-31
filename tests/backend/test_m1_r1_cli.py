from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, "-m", "pdu_exam_observer", *args],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def test_rehearse_r1_is_no_path_single_temp_root_and_reports_exact_ceiling() -> None:
    temp = Path(tempfile.gettempdir())
    before = {path.name for path in temp.glob("pdu-m1r1-rehearsal-*")}

    result = _run("rehearse-r1")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == {
        "authority_status": "AUTHORITY_NOT_ISSUED",
        "collection_authorized": False,
        "participant_collection_authorized": False,
        "production_reconciler_implemented": False,
        "production_reconciler_real_storage_verified": False,
        "production_reconciler_source_implemented": True,
        "real_data_deletion_authorized": False,
        "research_ready": False,
        "status": "M1_R1_RECONCILER_LOCALLY_VERIFIED_SYNTHETIC_ONLY",
        "synthetic_receipt_sha256": report["synthetic_receipt_sha256"],
    }
    assert len(report["synthetic_receipt_sha256"]) == 64
    assert "pdu-m1r1-rehearsal-" not in result.stdout
    assert {path.name for path in temp.glob("pdu-m1r1-rehearsal-*")} == before


def test_rehearse_r1_rejects_every_argument_and_migrate_apply_denies_without_config() -> None:
    rejected = _run("rehearse-r1", "--root", "C:/forbidden")
    denied = _run(
        "migrate-r1",
        "--apply",
        "--expected-readiness-digest",
        "0" * 64,
    )

    assert rejected.returncode == 2
    assert "--root" in rejected.stderr
    assert denied.returncode == 3
    assert denied.stdout.strip() == '{"authority_status":"AUTHORITY_NOT_ISSUED"}'
    assert "Traceback" not in rejected.stderr + denied.stderr
