"""Start only an owned local verification server; do not print its test PIN.

`--stop` terminates the recorded preview process tree and removes the owned
temporary workspace root after containment and marker checks.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/completion-2026-09-08"
STATE = OUT / "preview-server.json"


def _stop() -> int:
    if not STATE.is_file():
        print("No preview-server.json; nothing to stop")
        return 0
    metadata = json.loads(STATE.read_text(encoding="utf-8"))
    pid = int(metadata["pid"])
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        check=False,
    )
    root = Path(metadata["root"]).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if (
        temp_root in root.parents
        and root.name.startswith("PDUWorkspace-preview-")
        and (root / ".pdu-owned-verification").is_file()
    ):
        shutil.rmtree(root)
        print(f"Removed owned workspace root: {root}")
    else:
        print(f"Refused to remove unverified path: {root}")
    STATE.unlink()
    print("Preview stopped")
    return 0


if __name__ == "__main__":
    if "--stop" in sys.argv[1:]:
        raise SystemExit(_stop())
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
