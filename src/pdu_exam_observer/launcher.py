"""Local loopback launcher; deployment/binding remains outside the API factories."""

import os
import time
import webbrowser
from pathlib import Path
from threading import Thread

import uvicorn
from fastapi import FastAPI

from pdu_exam_observer.api.factories import AppConfig, create_exam_app, create_monitor_app
from pdu_exam_observer.configuration import load_native_config, validate_storage_root
from pdu_exam_observer.m1 import M1Backend
from pdu_exam_observer.m1_r1 import M1R1Backend
from pdu_exam_observer.m2_synthetic_review import SyntheticReviewService


def _port(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        port = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError(f"{name} must be between 1 and 65535")
    return port


def should_open_browser() -> bool:
    return os.getenv("PDU_OPEN_BROWSER", "1") != "0"


def build_apps_from_environment() -> tuple[FastAPI, FastAPI]:
    reviewer_pin = os.getenv("PDU_REVIEWER_PIN")
    if not reviewer_pin:
        raise RuntimeError("PDU_REVIEWER_PIN must be supplied by the launcher environment")
    exam_port = _port("PDU_EXAM_PORT", 8765)
    monitor_port = _port("PDU_MONITOR_PORT", 8766)
    if exam_port == monitor_port:
        raise RuntimeError("PDU_EXAM_PORT and PDU_MONITOR_PORT must differ")
    mode = os.getenv("PDU_RUNTIME_MODE", "m0").lower()
    if mode not in {"m0", "m1", "m1r1", "m2synthetic", "m2research"}:
        raise RuntimeError("PDU_RUNTIME_MODE must be m0, m1, m1r1, m2synthetic, or m2research")
    backend = None
    synthetic_review_service = None
    workspace = None
    if mode == "m1":
        native = load_native_config()
        backend = M1Backend(
            native.root,
            encryption_status=native.encryption_status,
            acl_status=native.acl_status,
        )
    elif mode == "m1r1":
        native = load_native_config()
        backend = M1R1Backend(
            native.root,
            encryption_status=native.encryption_status,
            acl_status=native.acl_status,
        )
    elif mode == "m2synthetic":
        synthetic_review_service = SyntheticReviewService.create_owned()
    elif mode == "m2research":
        from pdu_exam_observer.research_runtime import ResearchRuntimeService
        from pdu_exam_observer.showcase.model_import import ModelRegistry
        from pdu_exam_observer.workspace_service import WorkspaceBackend, WorkspaceService

        root_value = os.getenv("PDU_WORKSPACE_ROOT")
        if not root_value:
            raise RuntimeError("PDU_WORKSPACE_ROOT must be configured by the native launcher")
        root = Path(root_value)
        if not root.is_absolute() or str(root).startswith("\\\\"):
            raise RuntimeError("PDU_WORKSPACE_ROOT must be an absolute local directory")
        if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
            raise RuntimeError("PDU_WORKSPACE_ROOT cannot traverse symlinks")
        root = validate_storage_root(root, create=True)
        models = ModelRegistry(root / "models")
        runtime = ResearchRuntimeService(root / "research", model_provider=models.model_provider)
        try:
            backend = WorkspaceBackend(root / "exam", encryption_status="UNVERIFIED",
                                       acl_status="UNVERIFIED")
            workspace = WorkspaceService(root / "metadata", backend, runtime, models,
                                         authority_reference=os.getenv("PDU_COLLECTION_AUTHORITY_REF"))
        except Exception:
            runtime.close()
            if backend is not None:
                backend.store.close()
            raise
    if backend is None:
        config = AppConfig(
            reviewer_pin=reviewer_pin,
            exam_origin=f"http://127.0.0.1:{exam_port}",
            monitor_origin=f"http://localhost:{monitor_port}",
            allowed_hosts=("127.0.0.1", "localhost"),
            synthetic_review_service=synthetic_review_service,
        )
    else:
        config = AppConfig(
            reviewer_pin=reviewer_pin,
            exam_origin=f"http://127.0.0.1:{exam_port}",
            monitor_origin=f"http://localhost:{monitor_port}",
            allowed_hosts=("127.0.0.1", "localhost"),
            backend=backend,
            workspace=workspace,
        )
    try:
        return create_exam_app(config), create_monitor_app(config)
    except Exception:
        if workspace is not None:
            workspace.close()
        if synthetic_review_service is not None:
            synthetic_review_service.close()
        raise


def _close_synthetic_review_service(monitor: FastAPI) -> None:
    workspace = getattr(monitor.state, "workspace", None)
    if workspace is not None:
        workspace.close()
        backend = getattr(monitor.state, "backend", None)
        if isinstance(backend, M1Backend):
            backend.store.close()
    service = getattr(monitor.state, "synthetic_review_service", None)
    if service is not None:
        service.close()


def main() -> None:
    exam, monitor = build_apps_from_environment()
    exam_port = _port("PDU_EXAM_PORT", 8765)
    monitor_port = _port("PDU_MONITOR_PORT", 8766)
    monitor_server = uvicorn.Server(uvicorn.Config(monitor, host="localhost", port=monitor_port))
    exam_server = uvicorn.Server(uvicorn.Config(exam, host="127.0.0.1", port=exam_port))
    monitor_thread = Thread(target=monitor_server.run, name="pdu-monitor", daemon=True)
    exam_thread = Thread(target=exam_server.run, name="pdu-exam", daemon=True)
    monitor_thread.start()
    exam_thread.start()
    try:
        for _ in range(100):
            if monitor_server.started and exam_server.started:
                if should_open_browser():
                    query = "?workspace=1" if os.getenv("PDU_RUNTIME_MODE") == "m2research" else ""
                    webbrowser.open(f"http://localhost:{monitor_port}/monitor{query}")
                    webbrowser.open(f"http://127.0.0.1:{exam_port}/exam")
                break
            time.sleep(0.05)
        while monitor_thread.is_alive() and exam_thread.is_alive():
            time.sleep(0.2)
    finally:
        monitor_server.should_exit = True
        exam_server.should_exit = True
        monitor_thread.join(timeout=5)
        exam_thread.join(timeout=5)
        _close_synthetic_review_service(monitor)
