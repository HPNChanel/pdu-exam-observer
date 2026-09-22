"""Verify current manifests and a relocated packaged synthetic HTTP workflow."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.release_manifest import verify_manifest  # noqa: E402


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def cycle(bundle: Path, owned_root: Path, model: Path, base_port: int) -> dict[str, Any]:
    root = owned_root / "workspace"
    pin = "package-fixture-" + uuid.uuid4().hex
    system = Path(os.environ["SystemRoot"])
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        in {
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "COMSPEC",
            "USERPROFILE",
            "LOCALAPPDATA",
            "APPDATA",
        }
    }
    environment.update(
        {
            "PATH": str(system / "System32"),
            "PDU_RUNTIME_MODE": "m2research",
            "PDU_WORKSPACE_ROOT": str(root),
            "PDU_REVIEWER_PIN": pin,
            "PDU_OPEN_BROWSER": "0",
            "PDU_EXAM_PORT": str(base_port),
            "PDU_MONITOR_PORT": str(base_port + 1),
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "http://127.0.0.1:9",
            "NO_PROXY": "localhost,127.0.0.1",
        }
    )
    executable = bundle / "PDUWorkspace.exe"
    monitor_origin = f"http://localhost:{base_port + 1}"
    exam_origin = f"http://127.0.0.1:{base_port}"
    cookie_jar = __import__("http.cookiejar", fromlist=["CookieJar"]).CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(cookie_jar)
    )
    token = ""

    def request(
        path: str,
        *,
        monitor: bool = True,
        data: Any = None,
        method: str = "GET",
        content_type: str = "application/json",
        raw: bool = False,
    ) -> tuple[int, Any]:
        origin = monitor_origin if monitor else exam_origin
        headers = {"Origin": origin}
        if monitor and token:
            headers["Authorization"] = "Bearer " + token
        if method != "GET":
            headers["Idempotency-Key"] = uuid.uuid4().hex
            headers["Content-Type"] = content_type
            if not monitor:
                csrf = next(
                    (cookie.value for cookie in cookie_jar if cookie.name == "pdu_exam_csrf"), None
                )
                if csrf:
                    headers["X-CSRF-Token"] = csrf
        payload = (
            data
            if isinstance(data, bytes)
            else json.dumps(data).encode()
            if method != "GET"
            else None
        )
        query = urllib.request.Request(origin + path, data=payload, method=method, headers=headers)
        try:
            with opener.open(query, timeout=60) as response:
                value = response.read()
                return response.status, value if raw else json.loads(value) if value else None
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8", errors="replace")

    with (owned_root / "process.log").open("wb") as log:
        process = subprocess.Popen(
            [str(executable)],
            cwd=owned_root,
            env=environment,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError("PACKAGED_LAUNCH_FAILED")
                try:
                    if request("/api/v1/health")[0] == 200:
                        break
                except urllib.error.URLError:
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError("PACKAGED_LAUNCH_TIMEOUT")
                time.sleep(0.2)
            assert request("/api/v1/workspace")[0] == 401
            code, login = request("/api/v1/reviewer/login", data={"pin": pin}, method="POST")
            assert code == 200, login
            token = login["access_token"]
            code, imported = request(
                "/api/v1/workspace/models/import",
                data=model.read_bytes(),
                content_type="application/zip",
                method="POST",
            )
            assert code == 200, imported
            code, created = request(
                "/api/v1/workspace/sessions", data={"source_kind": "AI_RENDERED"}, method="POST"
            )
            assert code == 201, created
            sid, exam_id = created["session_id"], created["exam_session_id"]
            assert (
                request(
                    "/api/v1/candidate/pair",
                    monitor=False,
                    data={"pairing_code": created["pairing_code"]},
                    method="POST",
                )[0]
                == 200
            )
            for action in ("consent", "preflight"):
                assert (
                    request(f"/api/v1/sessions/{exam_id}/{action}", monitor=False, method="POST")[0]
                    == 200
                )
            for action in ("preflight", "start"):
                code, value = request(f"/api/v1/workspace/sessions/{sid}/{action}", method="POST")
                assert code == 200, value
            code, status = request("/api/v1/exam/status", monitor=False)
            assert code == 200 and status["state"] == "RECORDING"
            assert not {"research_label", "confidence", "model_version"} & set(status)
            assert (
                request(
                    "/api/v1/exam/answers",
                    monitor=False,
                    data={"answer_id": "fixture-q1-b", "question_id": "q1", "value": "B"},
                    method="POST",
                )[0]
                == 200
            )
            for action in ("stop", "seal"):
                code, value = request(f"/api/v1/workspace/sessions/{sid}/{action}", method="POST")
                assert code == 200, value
            _, detail = request(f"/api/v1/workspace/sessions/{sid}")
            for event in detail["events"]:
                _, current = request(f"/api/v1/workspace/sessions/{sid}")
                code, decision = request(
                    f"/api/v1/workspace/sessions/{sid}/decision",
                    data={
                        "event_id": event["event_id"],
                        "label": event["research_label"],
                        "review_status": "CONFIRMED",
                        "start_ms": event["start_ms"],
                        "end_ms": event["end_ms"],
                        "reason": "Packaged synthetic fixture only",
                        "expected_revision": current["revision"],
                    },
                    method="PUT",
                )
                assert code == 200, decision
            code, video = request(f"/api/v1/workspace/sessions/{sid}/preview", raw=True)
            assert code == 200 and b"ftyp" in video[:40]
            assert request(f"/api/v1/workspace/sessions/{sid}/lock", method="POST")[0] == 200
            code, exported = request(f"/api/v1/workspace/sessions/{sid}/export", raw=True)
            assert code == 200
            with zipfile.ZipFile(io.BytesIO(exported)) as archive:
                assert set(archive.namelist()) == {"manifest.json", "records.jsonl"}
                records = [json.loads(line) for line in archive.read("records.jsonl").splitlines()]
                assert records and all(record["source_kind"] == "AI_RENDERED" for record in records)
            assert request(f"/api/v1/workspace/sessions/{sid}/export", monitor=False)[0] == 404
            assert (
                request(f"/api/v1/workspace/sessions/{sid}/withdraw-test", method="POST")[0] == 200
            )
            assert not (root / "research/runtime-artifacts" / sid).exists()
            assert request(f"/api/v1/workspace/sessions/{sid}/export")[0] == 409
            with sqlite3.connect(root / "research/research-runtime.v1.sqlite3") as database:
                states = [
                    json.loads(row[0])
                    for row in database.execute(
                        "SELECT payload_json FROM runtime_events WHERE event_type='MODEL_STATE'"
                    )
                ]
            assert any(
                state.get("model_invoked") is True and state.get("model_version")
                for state in states
            ), states
            return {
                "status": "PASS",
                "source_kind": "AI_RENDERED",
                "record_count": len(records),
                "video_sha256": hashlib.sha256(video).hexdigest(),
                "export_sha256": hashlib.sha256(exported).hexdigest(),
                "model_inference_invoked": True,
                "model_inference_state": states[-1]["state"],
                "withdrawal_owned_artifacts_absent": True,
                "external_http_proxy": "UNREACHABLE",
                "child_path": "WINDOWS_SYSTEM32_ONLY",
                "python_node_on_child_path": False,
            }
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle.resolve(strict=True)
    detached = bundle.parent / "RELEASE_MANIFEST.detached.json"
    assert verify_manifest(bundle, bundle / "RELEASE_MANIFEST.json", detached)
    temporary = Path(tempfile.mkdtemp(prefix="PDU-package-verification-"))
    assert temporary.resolve().parent == Path(tempfile.gettempdir()).resolve()
    marker = temporary / ".pdu-owned"
    marker.write_text("packaged-synthetic-verification", encoding="ascii")
    try:
        original_work = temporary / "original-run"
        original_work.mkdir()
        first = cycle(bundle, original_work, args.model, 8891)
        moved = temporary / "Relocated folder with spaces" / "PDU-Workspace"
        shutil.copytree(bundle, moved)
        assert verify_manifest(moved, moved / "RELEASE_MANIFEST.json", detached)
        relocated_work = temporary / "relocated-run"
        relocated_work.mkdir()
        second = cycle(moved, relocated_work, args.model, 8893)
        assert verify_manifest(bundle, bundle / "RELEASE_MANIFEST.json", detached)
        receipt = {
            "schema_version": 1,
            "evidence_state": "OBSERVED",
            "status": "PASS",
            "bundle_manifest_sha256": digest(bundle / "RELEASE_MANIFEST.json"),
            "model_zip_sha256": digest(args.model),
            "original": first,
            "relocated": second,
            "same_host_only": True,
            "new_device_verified": False,
            "release_authorized": False,
            "network_interface_disabled": False,
            "network_scope": (
                "external HTTP proxy unavailable; packaged dependencies; loopback workflow"
            ),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2))
    finally:
        if (
            temporary.resolve().parent != Path(tempfile.gettempdir()).resolve()
            or not marker.is_file()
        ):
            raise RuntimeError("CLEANUP_SCOPE_INVALID")
        shutil.rmtree(temporary)


if __name__ == "__main__":
    main()
