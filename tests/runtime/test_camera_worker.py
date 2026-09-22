from __future__ import annotations

import multiprocessing as mp
import time
from queue import Full

import pytest

from pdu_exam_observer.research_runtime.camera_worker import (
    CaptureError,
    CaptureStartError,
    CaptureTimeout,
    NativeCapture,
)


def _finite_source(frame_queue: object, ready_queue: object, stop: object, _device: int) -> None:
    ready_queue.put(("READY",))  # type: ignore[union-attr]
    frame_queue.put_nowait(("FRAME", b"synthetic", 123, 2))  # type: ignore[union-attr]
    stop.wait(10)  # type: ignore[union-attr]


def _full_queue_source(
    frame_queue: object, ready_queue: object, stop: object, _device: int
) -> None:
    # Fill the bounded queue before READY so the consumer cannot drain a slot
    # before the producer's first post-fill put — the drop is deterministic.
    for index in range(2):
        frame_queue.put_nowait(("FRAME", bytes([index]), index, 0))  # type: ignore[union-attr]
    ready_queue.put(("READY",))  # type: ignore[union-attr]
    dropped = 0
    while not stop.is_set():  # type: ignore[union-attr]
        try:
            frame_queue.put_nowait(("FRAME", b"after-drop", 99, dropped))  # type: ignore[union-attr]
            break
        except Full:
            dropped += 1
            time.sleep(0.02)
    stop.wait(10)  # type: ignore[union-attr]


def _fault_source(_frame_queue: object, ready_queue: object, _stop: object, _device: int) -> None:
    ready_queue.put(("FAULT", "CAMERA_OPEN_FAILED"))  # type: ignore[union-attr]


def _runtime_fault_source(
    _frame_queue: object, ready_queue: object, _stop: object, _device: int
) -> None:
    ready_queue.put(("READY",))  # type: ignore[union-attr]
    ready_queue.put(("FAULT", "CAMERA_READ_FAILED"))  # type: ignore[union-attr]


def _silent_source(_frame_queue: object, _ready_queue: object, stop: object, _device: int) -> None:
    stop.wait(10)  # type: ignore[union-attr]


def _capture(target: object) -> NativeCapture:
    return NativeCapture(context=mp.get_context("spawn"), worker_target=target, startup_timeout=5.0)


def test_generated_source_returns_frame_metadata_and_closes_bounded() -> None:
    capture = _capture(_finite_source)
    capture.start()
    frame = capture.read(timeout=1.0)
    assert frame.frame == b"synthetic"
    assert frame.captured_ns == 123
    assert frame.dropped == 2
    assert tuple(frame) == (b"synthetic", 123, 2)
    capture.close()
    assert not capture.is_alive


def test_queue_pressure_reports_explicit_drops() -> None:
    capture = _capture(_full_queue_source)
    capture.start()
    first = capture.read(timeout=1.0)
    second = capture.read(timeout=1.0)
    third = capture.read(timeout=1.0)
    assert first.captured_ns < second.captured_ns
    assert third.dropped >= 1
    capture.close()


def test_start_fault_and_timeout_fail_without_native_detail() -> None:
    with pytest.raises(CaptureStartError, match="CAMERA_OPEN_FAILED"):
        _capture(_fault_source).start()
    with pytest.raises(CaptureStartError, match="CAPTURE_START_TIMEOUT"):
        NativeCapture(
            context=mp.get_context("spawn"), worker_target=_silent_source, startup_timeout=0.5
        ).start()


def test_runtime_fault_is_reported_without_waiting_for_read_timeout() -> None:
    capture = _capture(_runtime_fault_source)
    capture.start()
    began = time.monotonic()
    with pytest.raises(CaptureError, match="CAMERA_READ_FAILED"):
        capture.read(timeout=1.0)
    assert time.monotonic() - began < 0.5
    assert not capture.is_alive


def test_read_timeout_and_close_terminate_a_stuck_child() -> None:
    capture = _capture(_finite_source)
    capture.start()
    capture.read(timeout=1.0)
    with pytest.raises(CaptureTimeout, match="CAPTURE_READ_TIMEOUT"):
        capture.read(timeout=0.05)
    began = time.monotonic()
    capture.close(join_timeout=0.2)
    assert time.monotonic() - began < 2.0
    assert not capture.is_alive
