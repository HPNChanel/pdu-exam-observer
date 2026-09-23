"""Contract tests for the hermetic frontend stage in the completion builder.

The builder must construct the frontend artifact itself from the pinned
lockfile instead of trusting whatever bytes happen to sit in
``apps/web/dist`` — the failure mode that once packed a stale frontend
bundle. These tests pin the argv surface, toolchain resolution, and the
dist manifest recorded in the build receipt without running npm.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "build_completion_delivery.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_completion_delivery", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frontend_commands_are_fixed_argv_and_lockfile_pinned() -> None:
    builder = _load_builder()
    commands = builder.frontend_build_commands("npm")
    assert commands == [
        ["npm", "ci", "--no-audit", "--no-fund"],
        ["npm", "run", "build"],
    ]
    # npm ci (not npm install) so the pinned lockfile is enforced exactly.
    assert all(command[0] == "npm" for command in commands)
    assert all("shell" not in part.lower() for command in commands for part in command)


def test_required_tool_fails_closed_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _load_builder()
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="FRONTEND_TOOLCHAIN_UNAVAILABLE"):
        builder._required_tool("node")


def test_tool_version_rejects_failed_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _load_builder()

    def _failed(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _failed)
    with pytest.raises(RuntimeError, match="FRONTEND_TOOLCHAIN_UNAVAILABLE"):
        builder._tool_version("node")


def test_tool_version_returns_trimmed_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _load_builder()

    def _ok(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="v24.11.0\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _ok)
    assert builder._tool_version("node") == "v24.11.0"


def test_dist_manifest_hashes_every_file(tmp_path: Path) -> None:
    builder = _load_builder()
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    payload = b"fake-js"
    (dist / "index.html").write_bytes(b"<html></html>")
    (dist / "assets" / "index.js").write_bytes(payload)
    manifest = builder._dist_manifest(dist)
    assert manifest["file_count"] == 2
    entries = {entry["path"]: entry for entry in manifest["files"]}
    assert entries["assets/index.js"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert entries["index.html"]["bytes"] == 13


def test_dist_manifest_rejects_missing_or_empty_dist(tmp_path: Path) -> None:
    builder = _load_builder()
    with pytest.raises(RuntimeError, match="no dist directory"):
        builder._dist_manifest(tmp_path / "absent")
    (tmp_path / "empty").mkdir()
    with pytest.raises(RuntimeError, match="empty"):
        builder._dist_manifest(tmp_path / "empty")
