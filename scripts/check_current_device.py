"""Opt-in current-device technical probe. No images, audio or person data are saved."""

from __future__ import annotations

import ctypes
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import cv2


def probe(backend: str = "DSHOW") -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": 1,
        "evidence_state": "OBSERVED",
        "environment": platform.system(),
        "new_device_verified": False,
        "media_saved": False,
        "audio_opened": False,
        "participant_collection": False,
    }
    result["physical_display_count"] = (
        int(ctypes.windll.user32.GetSystemMetrics(80)) if platform.system() == "Windows" else None
    )
    result["backend"] = backend
    capture = cv2.VideoCapture(0, cv2.CAP_DSHOW if backend == "DSHOW" else cv2.CAP_MSMF)
    try:
        if not capture.isOpened():
            result.update(camera="UNAVAILABLE", reason="OPEN_FAILED")
            return result
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        capture.set(cv2.CAP_PROP_FPS, 15)
        stamps, shapes = [], []
        for _ in range(32):
            ok, frame = capture.read()
            if not ok or frame is None:
                result.update(camera="TECHNICAL_INSUFFICIENT", reason="READ_FAILED")
                return result
            stamps.append(time.monotonic())
            shapes.append((int(frame.shape[1]), int(frame.shape[0])))
        elapsed = stamps[-1] - stamps[2]
        result.update(
            camera="READY"
            if all(shape == (1280, 720) for shape in shapes)
            else "TECHNICAL_INSUFFICIENT",
            frame_count=len(shapes),
            observed_width=shapes[-1][0],
            observed_height=shapes[-1][1],
            requested_fps=15,
            reported_fps=capture.get(cv2.CAP_PROP_FPS),
            measured_read_fps=(len(stamps) - 3) / elapsed if elapsed > 0 else None,
            evidence_scope=(
                "short current-device frame-read probe; "
                "not a recording or long-session acceptance"
            ),
        )
        return result
    finally:
        capture.release()


if __name__ == "__main__":
    if "--child" in sys.argv:
        print(json.dumps(probe(sys.argv[-1])))
        raise SystemExit(0)
    output = (
        Path(__file__).resolve().parents[1] / "output/completion-2026-09-08/current-device.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    attempts = []
    for backend in ("DSHOW", "MSMF"):
        try:
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--child", backend],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            receipt = json.loads(completed.stdout)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError):
            receipt = {
                "backend": backend,
                "camera": "TECHNICAL_INSUFFICIENT",
                "reason": "PROBE_TIMEOUT_OR_DRIVER_FAILURE",
                "media_saved": False,
            }
        attempts.append(receipt)
        if receipt.get("camera") == "READY":
            break
    receipt = {
        "schema_version": 1,
        "attempts": attempts,
        "new_device_verified": False,
        "physical_display_count": int(ctypes.windll.user32.GetSystemMetrics(80)),
        "evidence_state": "OBSERVED",
        "participant_collection": False,
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
