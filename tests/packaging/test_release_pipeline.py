import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest


def test_build_release_does_not_pass_makespec_only_specpath_with_a_spec_file() -> None:
    script = (Path(__file__).parents[2] / "scripts" / "build_release.ps1").read_text(
        encoding="utf-8"
    )

    assert "--specpath" not in script
    assert "PDU-Exam-Observer.spec" in script


def test_pyinstaller_spec_resolves_project_root_from_spec_directory() -> None:
    spec = (Path(__file__).parents[2] / "packaging" / "PDU-Exam-Observer.spec").read_text(
        encoding="utf-8"
    )

    assert "Path(SPECPATH).resolve().parents[1]" not in spec
    assert "Path(SPECPATH).resolve().parent" in spec


def test_smoke_release_terminates_the_pyinstaller_process_tree() -> None:
    script = (Path(__file__).parents[2] / "scripts" / "smoke_release.ps1").read_text(
        encoding="utf-8"
    )

    assert "taskkill.exe /PID $process.Id /T /F" in script


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_smoke_release_forwards_custom_ports_to_packaged_runtime() -> None:
    if os.name != "nt":
        pytest.skip("The packaged Windows smoke test requires Windows.")

    project_root = Path(__file__).parents[2]
    executable = (
        project_root
        / "packaging"
        / "release"
        / "PDU-Exam-Observer"
        / "PDUExamObserver.exe"
    )
    if not executable.is_file():
        pytest.skip("Build the packaged executable before running this integration test.")

    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if powershell is None:
        pytest.skip("PowerShell is required for the packaged smoke test.")

    exam_port = _free_loopback_port()
    monitor_port = _free_loopback_port()
    while monitor_port == exam_port:
        monitor_port = _free_loopback_port()

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "smoke_release.ps1"),
            "-Executable",
            str(executable),
            "-ExamPort",
            str(exam_port),
            "-MonitorPort",
            str(monitor_port),
            "-TimeoutSeconds",
            "15",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "Smoke checks passed" in output
