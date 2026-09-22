"""Current-device check of the shipped bounded worker, with no media saved."""

from __future__ import annotations

import ctypes
import json
import multiprocessing
import tempfile
from pathlib import Path

from pdu_exam_observer.research_runtime import ResearchRuntimeService


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="PDU-camera-diagnostic-") as temporary:
        runtime = ResearchRuntimeService(Path(temporary))
        try:
            result = runtime.diagnose_current_camera()
        finally:
            runtime.close()
    result.update(
        schema_version=1,
        evidence_state="OBSERVED",
        physical_display_count=int(ctypes.windll.user32.GetSystemMetrics(80)),
        media_saved=False,
        participant_collection=False,
        audio_opened=False,
        new_device_verified=False,
    )
    destination = (
        Path(__file__).resolve().parents[1] / "output/completion-2026-09-08/workspace-camera.json"
    )
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
