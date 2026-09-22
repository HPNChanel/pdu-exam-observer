"""Bounded process ownership for the one native camera device.

Frames are internal parent/child messages only.  This module does not write
media, inspect identities, or log device details.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import time
from collections.abc import Callable
from typing import Any, NamedTuple


class CaptureError(RuntimeError):
    pass


class CaptureStartError(CaptureError):
    pass


class CaptureTimeout(CaptureError):
    pass


class CapturedFrame(NamedTuple):
    """The bounded parent-facing frame envelope.

    Being a ``NamedTuple`` preserves the integration contract: callers may
    unpack it as ``frame, captured_ns, dropped`` while tests and adapters can
    still use named fields.
    """

    frame: Any
    captured_ns: int
    dropped: int


WorkerTarget = Callable[[Any, Any, Any, int], None]


def _native_worker(frame_queue: Any, status_queue: Any, stop: Any, _device_index: int) -> None:
    """Top-level spawn target. Device zero is fixed; no browser input reaches it."""
    capture = None
    try:
        import cv2

        capture = cv2.VideoCapture(0, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(0)
        if not capture.isOpened():
            status_queue.put(("FAULT", "CAMERA_OPEN_FAILED"))
            return
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        capture.set(cv2.CAP_PROP_FPS, 15)
        status_queue.put(("READY",))
        dropped = 0
        while not stop.is_set():
            okay, frame = capture.read()
            if not okay or frame is None:
                status_queue.put(("FAULT", "CAMERA_READ_FAILED"))
                return
            try:
                frame_queue.put_nowait(("FRAME", frame, time.perf_counter_ns(), dropped))
                dropped = 0
            except queue.Full:
                dropped += 1
    except Exception:
        # Do not expose driver/library text through an API or log.
        try:
            status_queue.put(("FAULT", "CAMERA_WORKER_FAILED"))
        except Exception:
            pass
    finally:
        if capture is not None:
            capture.release()


class NativeCapture:
    """Parent-side process controller with bounded start, read, and close calls."""

    def __init__(
        self,
        *,
        context: Any | None = None,
        worker_target: WorkerTarget = _native_worker,
        startup_timeout: float = 3.0,
    ) -> None:
        if startup_timeout <= 0:
            raise ValueError("startup_timeout must be positive")
        self._context = context or mp.get_context("spawn")
        self._target = worker_target
        self._startup_timeout = startup_timeout
        self._frame_queue: Any | None = None
        self._status_queue: Any | None = None
        self._stop: Any | None = None
        self._process: Any | None = None

    @property
    def is_alive(self) -> bool:
        return bool(self._process is not None and self._process.is_alive())

    def start(self) -> None:
        if self._process is not None:
            raise CaptureStartError("CAPTURE_ALREADY_STARTED")
        self._frame_queue = self._context.Queue(maxsize=2)
        self._status_queue = self._context.Queue(maxsize=1)
        self._stop = self._context.Event()
        self._process = self._context.Process(
            target=self._target,
            args=(self._frame_queue, self._status_queue, self._stop, 0),
            daemon=True,
        )
        self._process.start()
        try:
            status = self._status_queue.get(timeout=self._startup_timeout)
        except queue.Empty as exc:
            self.close()
            raise CaptureStartError("CAPTURE_START_TIMEOUT") from exc
        if not isinstance(status, tuple) or not status:
            self.close()
            raise CaptureStartError("CAPTURE_START_INVALID")
        if status[0] == "READY":
            return
        self.close()
        code = (
            status[1] if len(status) == 2 and isinstance(status[1], str) else "CAMERA_START_FAILED"
        )
        raise CaptureStartError(code)

    def read(self, *, timeout: float = 3.0) -> CapturedFrame:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if self._frame_queue is None or self._process is None:
            raise CaptureTimeout("CAPTURE_NOT_STARTED")
        deadline = time.monotonic() + timeout
        item: Any
        while True:
            try:
                status = self._status_queue.get_nowait() if self._status_queue is not None else None
            except queue.Empty:
                status = None
            if status is not None:
                self.close()
                code = (
                    status[1]
                    if isinstance(status, tuple) and len(status) == 2 and isinstance(status[1], str)
                    else "CAMERA_RUNTIME_FAILED"
                )
                raise CaptureError(code)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if not self._process.is_alive():
                    raise CaptureTimeout("CAPTURE_WORKER_STOPPED")
                raise CaptureTimeout("CAPTURE_READ_TIMEOUT")
            try:
                item = self._frame_queue.get(timeout=min(remaining, 0.05))
                break
            except queue.Empty:
                continue
        if (
            not isinstance(item, tuple)
            or len(item) != 4
            or item[0] != "FRAME"
            or not isinstance(item[2], int)
            or not isinstance(item[3], int)
            or item[3] < 0
        ):
            raise CaptureTimeout("CAPTURE_FRAME_INVALID")
        return CapturedFrame(item[1], item[2], item[3])

    def close(self, *, join_timeout: float = 3.0) -> None:
        if join_timeout <= 0:
            raise ValueError("join_timeout must be positive")
        process, self._process = self._process, None
        if self._stop is not None:
            self._stop.set()
        if process is not None:
            process.join(timeout=join_timeout)
            if process.is_alive():
                process.terminate()
                process.join(timeout=join_timeout)
        for item_name in ("_frame_queue", "_status_queue"):
            item = getattr(self, item_name)
            setattr(self, item_name, None)
            if item is not None:
                item.close()
                item.join_thread()
        self._stop = None

    def __enter__(self) -> NativeCapture:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
