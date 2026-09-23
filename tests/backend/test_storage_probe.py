"""Tests for the standard-user storage-controls probe (M2b remediation).

The probe reports VERIFIED only for directly observed evidence; everything
else degrades to UNKNOWN. icacls is used to build real DACL states — the
suite is Windows-only already.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import pdu_exam_observer.launcher as launcher
from pdu_exam_observer import configuration
from pdu_exam_observer.configuration import probe_storage_controls

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows-only storage probe")


def _icacls(*arguments: str) -> None:
    completed = subprocess.run(
        ("icacls", *arguments), capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_probe_returns_honest_vocabulary_and_never_raises(tmp_path: Path) -> None:
    result = probe_storage_controls(tmp_path)
    assert set(result) == {"encryption_status", "acl_status"}
    assert set(result.values()) <= {"VERIFIED", "UNKNOWN"}
    assert probe_storage_controls(tmp_path / "does-not-exist") == {
        "encryption_status": "UNKNOWN",
        "acl_status": "UNKNOWN",
    }


def test_probe_degrades_to_unknown_on_internal_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        configuration, "_probe_acl", lambda _root: (_ for _ in ()).throw(OSError("x"))
    )
    result = probe_storage_controls(tmp_path)
    assert result["acl_status"] == "UNKNOWN"
    assert result["encryption_status"] in {"VERIFIED", "UNKNOWN"}


def test_acl_probe_verified_only_when_broad_sids_grant_nothing(tmp_path: Path) -> None:
    restricted = tmp_path / "restricted"
    restricted.mkdir()
    _icacls(
        str(restricted), "/inheritance:r", "/grant:r", f"{os.getlogin()}:(OI)(CI)F"
    )
    broad = tmp_path / "broad"
    broad.mkdir()
    _icacls(str(broad), "/grant", "Everyone:(OI)(CI)R")

    assert configuration._probe_acl(restricted) == "VERIFIED"
    assert configuration._probe_acl(broad) == "UNKNOWN"


def test_encryption_probe_marks_only_observed_efs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FILE_ATTRIBUTE_ENCRYPTED (0x4000) observed on the root -> VERIFIED;
    # anything else stays UNKNOWN (BitLocker is not determinable as a
    # standard user).
    plain = tmp_path / "plain"
    plain.mkdir()
    assert configuration._probe_encryption(plain) == "UNKNOWN"

    class FakeStat:
        st_file_attributes = 0x4000

    monkeypatch.setattr(Path, "stat", lambda self, **kw: FakeStat())
    assert configuration._probe_encryption(plain) == "VERIFIED"


def test_launcher_passes_probed_controls_to_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pdu_exam_observer import workspace_service

    captured: dict[str, str] = {}
    real_init = workspace_service.WorkspaceBackend.__init__

    def spy_init(
        self: object,
        root: Path,
        *,
        encryption_status: str,
        acl_status: str,
        **kwargs: object,
    ) -> None:
        captured["encryption_status"] = encryption_status
        captured["acl_status"] = acl_status
        real_init(
            self,  # type: ignore[arg-type]
            root,
            encryption_status=encryption_status,
            acl_status=acl_status,
            **kwargs,  # type: ignore[arg-type]
        )

    monkeypatch.setenv("PDU_REVIEWER_PIN", "test-only-pin")
    monkeypatch.setenv("PDU_RUNTIME_MODE", "m2research")
    monkeypatch.setenv("PDU_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("PDU_OPEN_BROWSER", "0")
    monkeypatch.setattr(workspace_service.WorkspaceBackend, "__init__", spy_init)
    monkeypatch.setattr(
        launcher,
        "probe_storage_controls",
        lambda _root: {"encryption_status": "VERIFIED", "acl_status": "VERIFIED"},
    )
    launcher.build_apps_from_environment()
    assert captured == {"encryption_status": "VERIFIED", "acl_status": "VERIFIED"}


def test_probe_on_launcher_root_shape(tmp_path: Path) -> None:
    # The launcher probes the operator-selected root; make sure a real
    # workspace-shaped tree probes without error.
    (tmp_path / "exam").mkdir()
    (tmp_path / "research").mkdir()
    result = probe_storage_controls(tmp_path)
    assert set(result.values()) <= {"VERIFIED", "UNKNOWN"}
    if sys.platform == "win32":
        # A fresh user temp dir typically inherits broad ACEs -> UNKNOWN is
        # the expected honest answer; VERIFIED is acceptable on locked-down
        # profiles. Either way the vocabulary is honest.
        assert result["acl_status"] in {"VERIFIED", "UNKNOWN"}
