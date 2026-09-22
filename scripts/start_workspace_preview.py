"""Start only an owned local verification server; do not print its test PIN."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/completion-2026-09-08"

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    workspace_root = Path(tempfile.mkdtemp(prefix="PDUWorkspace-preview-"))
    (workspace_root / ".pdu-owned-verification").write_text(
        "completion-2026-09-08", encoding="ascii"
    )
    env = {
        **os.environ,
        "PDU_RUNTIME_MODE": "m2research",
        "PDU_WORKSPACE_ROOT": str(workspace_root),
        "PDU_OPEN_BROWSER": "0",
        "PDU_REVIEWER_PIN": "workspace-verification-only",
        "PDU_EXAM_PORT": "8875",
        "PDU_MONITOR_PORT": "8876",
    }
    with (OUT / "preview-server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "pdu_exam_observer"],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    (OUT / "preview-server.json").write_text(
        json.dumps(
            {
                "pid": process.pid,
                "root": str(workspace_root),
                "exam": "http://127.0.0.1:8875/exam",
                "monitor": "http://localhost:8876/monitor?workspace=1",
            }
        ),
        encoding="utf-8",
    )
    print(f"Owned preview process started: {process.pid}")
