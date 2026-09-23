"""Discriminating coverage for CLI dispatch and validation surfaces."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pdu_exam_observer import workspace_cli

REPOSITORY = Path(__file__).resolve().parents[2]

_ENV_KEYS = (
    "PDU_WORKSPACE_ROOT",
    "PDU_RUNTIME_MODE",
    "PDU_OPEN_BROWSER",
    "PDU_REVIEWER_PIN",
)


@pytest.fixture
def preserve_process_env():
    saved = {key: os.environ.get(key) for key in _ENV_KEYS}
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _run_module(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = dict(os.environ)
    for key in _ENV_KEYS:
        merged.pop(key, None)
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, "-m", "pdu_exam_observer", *args],
        capture_output=True,
        text=True,
        env=merged,
        cwd=REPOSITORY,
        timeout=60,
    )


def test_main_dispatches_authority_template(tmp_path: Path) -> None:
    session_id = "6a840ce2-e8c8-4160-9836-0b56f72b63b9"
    result = _run_module("authority-template", "--root", str(tmp_path), "--session-id", session_id)
    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["authority_reference"] == "REPLACE_WITH_NATIVE_REFERENCE"
    assert document["session_pseudonym"] == session_id
    assert document["status"] == "DRAFT"


def test_main_dispatches_workspace_help() -> None:
    result = _run_module("workspace", "--help")
    assert result.returncode == 0
    assert "--root" in result.stdout


def test_main_dispatches_authority_install_help() -> None:
    result = _run_module("authority", "--help")
    assert result.returncode == 0
    assert "--record" in result.stdout


@pytest.mark.usefixtures("preserve_process_env")
def test_workspace_cli_rejects_relative_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDU_REVIEWER_PIN", "123456")
    with pytest.raises(SystemExit) as exc:
        workspace_cli.main(["--root", "relative/path"])
    assert exc.value.code == 2


@pytest.mark.usefixtures("preserve_process_env")
def test_workspace_cli_rejects_short_pin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PDU_REVIEWER_PIN", raising=False)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "12345")
    with pytest.raises(SystemExit) as exc:
        workspace_cli.main(["--root", str(tmp_path)])
    assert exc.value.code == 2
    assert "PDU_REVIEWER_PIN" not in os.environ


@pytest.mark.usefixtures("preserve_process_env")
def test_workspace_cli_happy_path_cleans_pin_in_finally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launched: list[dict[str, str]] = []
    monkeypatch.delenv("PDU_REVIEWER_PIN", raising=False)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "123456")
    import pdu_exam_observer.launcher as launcher

    monkeypatch.setattr(launcher, "main", lambda: launched.append(dict(os.environ)))
    workspace_cli.main(["--root", str(tmp_path), "--no-browser"])
    assert launched, "launcher main must be invoked exactly once"
    inside = launched[0]
    assert inside["PDU_REVIEWER_PIN"] == "123456"
    assert inside["PDU_RUNTIME_MODE"] == "m2research"
    assert inside["PDU_WORKSPACE_ROOT"] == str(tmp_path)
    assert inside["PDU_OPEN_BROWSER"] == "0"
    assert "PDU_REVIEWER_PIN" not in os.environ


@pytest.mark.usefixtures("preserve_process_env")
def test_workspace_cli_cleans_pin_when_launcher_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PDU_REVIEWER_PIN", raising=False)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "123456")
    import pdu_exam_observer.launcher as launcher

    def boom() -> None:
        raise RuntimeError("launch failed")

    monkeypatch.setattr(launcher, "main", boom)
    with pytest.raises(RuntimeError):
        workspace_cli.main(["--root", str(tmp_path)])
    assert "PDU_REVIEWER_PIN" not in os.environ


def test_run_all_gates_help_is_bounded() -> None:
    script = REPOSITORY / "scripts" / "run_all_gates.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        cwd=REPOSITORY,
        timeout=60,
    )
    assert result.returncode == 0
    assert "--keep-going" in result.stdout
    assert "--skip-frontend" in result.stdout
    assert "--skip-pytest" in result.stdout


def test_run_all_gates_step_surface_is_fixed_argv() -> None:
    import importlib.util

    script = REPOSITORY / "scripts" / "run_all_gates.py"
    spec = importlib.util.spec_from_file_location("run_all_gates", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    steps = module.build_steps("/venv/python", "npm", skip_pytest=False, skip_frontend=False)
    gates = [step.gate for step in steps]
    assert gates == [
        "pytest",
        "frontend-typecheck",
        "frontend-lint",
        "frontend-test",
        "frontend-build",
        "ruff",
        "mypy",
    ]
    assert all(isinstance(step.argv, tuple) for step in steps)
    assert all(step.argv[0] in {"/venv/python", "npm"} for step in steps)
    assert [step.gate for step in module.build_steps("/venv/python", "npm", True, True)] == [
        "ruff",
        "mypy",
    ]


def test_training_cli_research_requires_export_and_freeze(tmp_path: Path) -> None:
    missing_both = subprocess.run(
        [
            sys.executable,
            "-m",
            "research.training.showcase.v3.cli",
            "--mode",
            "RESEARCH",
            "--output",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        cwd=REPOSITORY,
        timeout=60,
    )
    assert missing_both.returncode == 2
    assert "--export" in missing_both.stderr
    missing_freeze = subprocess.run(
        [
            sys.executable,
            "-m",
            "research.training.showcase.v3.cli",
            "--mode",
            "RESEARCH",
            "--output",
            str(tmp_path / "out"),
            "--export",
            str(tmp_path / "export.zip"),
        ],
        capture_output=True,
        text=True,
        cwd=REPOSITORY,
        timeout=60,
    )
    assert missing_freeze.returncode == 2
    assert "--protocol-freeze" in missing_freeze.stderr
