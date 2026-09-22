from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

# ruff: noqa: E402, I001

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_m2_s3e_handoff_pack as builder
from scripts import run_m2_s3e_same_host_portability as harness


STATUS = (
    "M2_S3E_A_SAME_HOST_ISOLATED_PORTABILITY_LOCALLY_VERIFIED_"
    "CLEAN_ENVIRONMENT_HANDOFF_READY_DEVICE_UNVERIFIED_NO_RELEASE_AUTHORITY"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_builder_cli_is_closed_and_pins_exact_s3d_inputs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert builder.STATUS == STATUS
    assert builder.S3D_HASHES == {
        "build_validation_sha256": (
            "432c906b2a32d84d5d82509d27cfa3882500657ce97e544e7fb71513b0754b94"
        ),
        "executable_sha256": "9d9aabe6b6176fabb1db423924d8c27a8ee9478d302b421680dc8bfc989c66aa",
        "manifest_sha256": "8702963dddd8b9d2761120fce8875d9fd181177eb15f1576e72e7354ad3ae216",
        "round_trip_receipt_sha256": (
            "4d8a862408aec0470d86b084f1abdc9baa323a3ee53cb57dfe780c3d6e2258ed"
        ),
        "tree_sha256": "64686518c09679f98b6f3c01805535ca9aad50413781424a08020c2460d017e1",
    }
    assert builder.parse_mode([]) == "check"
    assert builder.parse_mode(["--build"]) == "build"
    with pytest.raises(builder.HandoffError, match="REQUEST_INVALID"):
        builder.parse_mode(["--output", "elsewhere"])
    assert capsys.readouterr().err == ""


def test_zip_builder_is_byte_deterministic_with_fixed_metadata() -> None:
    entries = {
        "README_M2_S3E_HANDOFF.txt": b"boundary\n",
        "PDU-Exam-Observer/PDUExamObserver.exe": b"binary",
    }
    first = builder.build_zip_bytes(entries)
    second = builder.build_zip_bytes(dict(reversed(tuple(entries.items()))))
    assert first == second
    with zipfile.ZipFile(BytesIO(first)) as archive:
        infos = archive.infolist()
        assert [item.filename for item in infos] == sorted(entries)
        assert all(item.date_time == builder.ZIP_TIMESTAMP for item in infos)
        assert all(item.create_system == 3 for item in infos)
        assert all(item.external_attr == builder.ZIP_FILE_EXTERNAL_ATTR for item in infos)


def test_zip_validator_rejects_traversal_duplicate_and_link_members() -> None:
    valid = builder.build_zip_bytes(
        {
            "README_M2_S3E_HANDOFF.txt": b"boundary\n",
            "PDU-Exam-Observer/PDUExamObserver.exe": b"binary",
        }
    )
    assert builder.inspect_zip_bytes(valid) == {
        "PDU-Exam-Observer/PDUExamObserver.exe": b"binary",
        "README_M2_S3E_HANDOFF.txt": b"boundary\n",
    }
    with pytest.raises(builder.HandoffError, match="ZIP_ENTRY_INVALID"):
        builder.build_zip_bytes({"../escape.txt": b"x"})
    duplicate = BytesIO()
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr("same.txt", b"a")
            archive.writestr("same.txt", b"b")
    with pytest.raises(builder.HandoffError, match="ZIP_ENTRY_INVALID"):
        builder.inspect_zip_bytes(duplicate.getvalue())
    link = BytesIO()
    with zipfile.ZipFile(link, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        archive.writestr(info, b"target")
    with pytest.raises(builder.HandoffError, match="ZIP_ENTRY_INVALID"):
        builder.inspect_zip_bytes(link.getvalue())


def test_powershell_verifier_is_no_argument_and_fixed_relative_path() -> None:
    source = builder.POWERSHELL_SOURCE.read_text(encoding="utf-8")
    required = (
        "$PSScriptRoot",
        "$script:ScriptArgumentCount -ne 0",
        "PDU_RUNTIME_MODE",
        "m2synthetic-reproduce",
        "M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.json",
        "UNVERIFIED_PENDING_SOURCE_IMPORT",
        "LOOPBACK_ONLY_OBSERVED",
    )
    assert all(marker in source for marker in required)
    forbidden = ("Invoke-Expression", "Start-BitsTransfer", "http://0.0.0.0")
    assert not any(marker in source for marker in forbidden)
    assert "$receipt = $run.receipt" in source
    assert "$run.integration_status" not in source
    assert "$run.observation_count" not in source
    assert "Assert-IntegrationReceiptAuthority $receipt" in source
    assert "Assert-AuthorityEnvelope $receipt" not in source


def test_powershell_contract_is_standard_user_system_path_and_loopback_only() -> None:
    source = builder.POWERSHELL_SOURCE.read_text(encoding="utf-8")
    required = (
        "WindowsBuiltInRole]::Administrator",
        "PROCESS_NOT_STANDARD_USER",
        "System32",
        "WindowsPowerShell\\v1.0",
        "127.0.0.1",
        "localhost",
        "Get-NetTCPConnection",
        "air_gapped_machine_verified",
        "clean_machine_verified",
    )
    assert all(marker in source for marker in required)
    assert "Set-NetFirewall" not in source
    assert "New-NetFirewall" not in source
    assert "$listeners.Count -ne 2" not in source
    assert "$observedPorts.Count -ne $Ports.Count" in source


def test_full_cycle_response_has_exact_accounting_and_closed_authority() -> None:
    document = harness.canonical_recorded_response()
    projection = harness.validate_response(document)
    assert projection == harness.canonical_recorded_projection()
    body = document["body"]
    assert body["run_contract"] == {
        "candidate_process_count": 3,
        "full_cycle_count": 1,
        "nominal_observation_count": 18077,
        "preflight_observation_count": 977,
        "reproduction_count": 2,
    }
    assert body["environment_observations"]["network_scope"] == "LOOPBACK_ONLY_OBSERVED"
    assert body["authority_ceiling"]["clean_machine_verified"] is False
    assert body["authority_ceiling"]["authority_status"] == "AUTHORITY_NOT_ISSUED"


def test_harness_runs_two_profiles_and_requires_identical_projections() -> None:
    class Adapter:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def run_relocation(self, profile: str) -> dict[str, Any]:
            self.calls.append(profile)
            return harness.canonical_recorded_response()

    adapter = Adapter()
    receipt = harness.run_with_adapter(adapter, harness.canonical_fixed_inputs())
    assert adapter.calls == ["PATH_WITH_SPACES", "UNICODE_PATH_WITH_SPACES"]
    assert receipt.status == STATUS
    assert receipt.body["reproducibility"]["byte_identical"] is True
    assert receipt.body["runtime_boundary"]["candidate_process_count"] == 6
    assert receipt.body["authority_ceiling"]["same_host_portable_verified"] is True


def test_failures_are_bounded_and_owned_cleanup_rejects_escape(tmp_path: Path) -> None:
    failure = harness.failure_document(harness.SameHostPortabilityFailureCode.RESPONSE_INVALID)
    encoded = harness.canonical_bytes(failure)
    assert encoded.endswith(b"\n")
    assert str(tmp_path).encode() not in encoded
    assert b"traceback" not in encoded.lower()
    parent = tmp_path / "owned"
    parent.mkdir()
    child = parent / "child"
    child.mkdir()
    (child / harness.OWNERSHIP_MARKER).write_text("owned\n", encoding="utf-8")
    harness.safe_cleanup_root(child, parent)
    assert not child.exists()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(harness.PortabilityError, match="TEMP_CLEANUP_FAILED"):
        harness.safe_cleanup_root(outside, parent)


def test_recorded_receipt_is_canonical_and_keeps_gap_06_and_08_open() -> None:
    path = ROOT / "docs" / "ai" / "M2_S3E_A_SAME_HOST_PORTABILITY.json"
    payload = path.read_bytes()
    document = json.loads(payload)
    assert payload == harness.canonical_bytes(document)
    assert document["status"] == STATUS
    body = document["body"]
    assert document["body_sha256"] == hashlib.sha256(
        harness.canonical_bytes(body, trailing_lf=False)
    ).hexdigest()
    gaps = {item["gap_id"]: item["status"] for item in body["gap_projection"]}
    assert gaps["GAP-06_CURRENT_SOURCE_MANIFEST_METADATA_AND_RECEIPTS_ABSENT"] == "OPEN"
    assert gaps["GAP-08_CLEAN_MACHINE_OR_VM_RECEIPT_ABSENT"] == "OPEN"
    authority = body["authority_ceiling"]
    assert authority["same_host_portable_verified"] is True
    assert authority["clean_environment_handoff_ready"] is True
    assert authority["clean_machine_verified"] is False
    assert authority["distribution_ready"] is False
    assert authority["release_authorized"] is False


def test_proposal_historical_and_s3b_through_s3d_inputs_remain_immutable() -> None:
    assert _sha256(ROOT / "docs/source/DE_CUONG_CHUA_CHINH_THUC_2026-08-23.docx") == (
        "2cd5f6fdb17d70fd5593e50b8387bc38dabf70430dfffecdbe64439dc884afd5"
    )
    assert _sha256(ROOT / "docs/ai/M2_S3D_PACKAGED_EVIDENCE_ROUND_TRIP.json") == (
        builder.S3D_HASHES["round_trip_receipt_sha256"]
    )
    assert _sha256(builder.S3D_BUILD_VALIDATION) == builder.S3D_HASHES["build_validation_sha256"]
    assert _sha256(builder.S3D_EXECUTABLE) == builder.S3D_HASHES["executable_sha256"]
    assert _sha256(builder.S3D_DETACHED_MANIFEST) == builder.S3D_HASHES["manifest_sha256"]
    assert builder.current_s3d_tree_sha256() == builder.S3D_HASHES["tree_sha256"]
    assert _sha256(ROOT / "docs/ai/M2_S3B_PACKAGE_INTEGRATION.json") == (
        "bef341dc251edf45c12a707e3c47e32f0d4c7127bf4f78e950a47cba170afcbd"
    )
    assert _sha256(ROOT / "docs/ai/M2_S3C_PACKAGED_SYNTHETIC_SMOKE.json") == (
        "479aa2e364216a8f4560fbf98a31a6935829d847dfbace65f7c66fae8778bbb7"
    )
