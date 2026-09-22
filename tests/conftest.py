"""Shared pytest fixtures for the runtime/backend suites.

The runtime no longer resolves ffmpeg from PATH (supply-chain control); the
encoder accepts only a bundled binary or an env-pinned absolute path with a
SHA-256 allowlist. Tests that exercise the real transcode path pin the
machine's ffmpeg explicitly through that contract instead of relying on
implicit PATH discovery. Tests that verify the refusal path clear the env
themselves with monkeypatch.delenv.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _pinned_ffmpeg_env(monkeypatch: pytest.MonkeyPatch) -> None:
    discovered = shutil.which("ffmpeg")
    if discovered is None:
        return
    binary = Path(discovered).resolve()
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    monkeypatch.setenv("PDU_FFMPEG_PATH", str(binary))
    monkeypatch.setenv("PDU_FFMPEG_SHA256", digest)
