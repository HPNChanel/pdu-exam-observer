"""Run the canonical local gate sequence and capture every output.

Orchestration only — no gate semantics live here. Each step runs with a
fixed argv list and pinned cwd (no shell), streams output to both the
console and a per-gate file (tee-style so a hung gate stays observable),
and the run ends with a machine-readable ``gate-summary.json``.

Usage:
    .venv/Scripts/python.exe scripts/run_all_gates.py
        [--output DIR] [--python EXE] [--npm EXE]
        [--keep-going] [--skip-frontend] [--skip-pytest]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Step:
    gate: str
    argv: tuple[str, ...]
    cwd: Path
    output_file: str


def build_steps(python: str, npm: str, skip_pytest: bool, skip_frontend: bool) -> list[Step]:
    web = ROOT / "apps" / "web"
    steps: list[Step] = []
    if not skip_pytest:
        steps.append(
            Step("pytest", (python, "-m", "pytest", "tests", "-q"), ROOT, "pytest-full.txt")
        )
    if not skip_frontend:
        steps.extend(
            [
                Step(
                    "frontend-typecheck",
                    (npm, "run", "typecheck"),
                    web,
                    "frontend-gates.txt",
                ),
                Step("frontend-lint", (npm, "run", "lint"), web, "frontend-gates.txt"),
                Step("frontend-test", (npm, "test", "--", "--run"), web, "frontend-gates.txt"),
                Step("frontend-build", (npm, "run", "build"), web, "frontend-gates.txt"),
            ]
        )
    steps.extend(
        [
            Step("ruff", (python, "-m", "ruff", "check", "."), ROOT, "ruff.txt"),
            Step("mypy", (python, "-m", "mypy"), ROOT, "mypy.txt"),
        ]
    )
    return steps


def _run_step(step: Step, output_dir: Path) -> dict[str, object]:
    relative_cwd = Path(step.cwd).relative_to(ROOT).as_posix() if step.cwd != ROOT else "."
    header = f"$ {relative_cwd}> {' '.join(step.argv)}"
    print(header, flush=True)
    started = time.monotonic()
    with (output_dir / step.output_file).open("a", encoding="utf-8") as sink:
        sink.write(header + "\n")
        process = subprocess.Popen(
            list(step.argv),
            cwd=step.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            sink.write(line)
        exit_code = process.wait()
        duration = time.monotonic() - started
        sink.write(f"[exit {exit_code} after {duration:.1f}s]\n\n")
    print(f"[{step.gate}] exit {exit_code} after {duration:.1f}s", flush=True)
    return {
        "gate": step.gate,
        "command": list(step.argv),
        "cwd": str(step.cwd),
        "exit_code": exit_code,
        "duration_s": round(duration, 3),
    }


def main() -> int:
    # Console output may hit a narrow OEM codepage (e.g. cp1252 cannot encode
    # vitest's U+2713); degrade console glyphs, never crash — per-gate files
    # still receive the exact utf-8 bytes.
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / f"gates-{datetime.now(UTC):%Y%m%d}",
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--npm", default=None)
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    npm = args.npm
    if not args.skip_frontend and npm is None:
        npm = shutil.which("npm")
        if npm is None:
            parser.error("FRONTEND_TOOLCHAIN_UNAVAILABLE: npm not found on PATH")

    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    steps = build_steps(args.python, npm or "npm", args.skip_pytest, args.skip_frontend)
    results = []
    for step in steps:
        result = _run_step(step, output_dir)
        results.append(result)
        if result["exit_code"] != 0 and not args.keep_going:
            break

    status = "PASS" if results and all(item["exit_code"] == 0 for item in results) else "FAIL"
    summary = {
        "schema_version": 1,
        "status": status,
        "run_started_utc": datetime.now(UTC).isoformat(),
        "python": str(Path(args.python).resolve()),
        "gates": results,
        "skipped": [
            name
            for name, flag in (("pytest", args.skip_pytest), ("frontend", args.skip_frontend))
            if flag
        ],
        "stop_on_failure": not args.keep_going,
    }
    summary_path = output_dir / "gate-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"gate-summary: {summary_path} -> {status}", flush=True)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
