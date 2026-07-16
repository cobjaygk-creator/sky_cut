"""In-process FIFO-ish gate for blog Phase-2 renders (TTS + Remotion/FFmpeg).

FastAPI BackgroundTasks still schedule work on the threadpool; this module
limits how many of those jobs run at once so Chromium/Remotion and FFmpeg
do not stampede on a local machine.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_slots: threading.Semaphore | None = None
_slots_init_lock = threading.Lock()
_stats_lock = threading.Lock()
_waiting = 0
_active = 0
_max_concurrent = 1
_completed = 0


def _ensure_slots() -> threading.Semaphore:
    global _slots, _max_concurrent
    if _slots is not None:
        return _slots
    with _slots_init_lock:
        if _slots is None:
            _max_concurrent = max(1, int(settings.blog_render_max_concurrent))
            _slots = threading.Semaphore(_max_concurrent)
            logger.info("Blog render queue ready max_concurrent=%s", _max_concurrent)
    return _slots


def render_queue_stats() -> dict[str, Any]:
    """Snapshot for /health operators."""
    _ensure_slots()
    with _stats_lock:
        return {
            "max_concurrent": _max_concurrent,
            "active": _active,
            "waiting": _waiting,
            "completed": _completed,
        }


def run_with_render_slot(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Acquire a render slot, run fn, release. Safe to pass to BackgroundTasks.add_task."""
    slots = _ensure_slots()
    label = getattr(fn, "__name__", "job")
    if args:
        label = f"{label}:{args[0]}"

    global _waiting, _active, _completed
    with _stats_lock:
        _waiting += 1
        waiting_now = _waiting
        active_now = _active
    logger.info(
        "Render queue enqueue label=%s waiting=%s active=%s max=%s",
        label,
        waiting_now,
        active_now,
        _max_concurrent,
    )

    started_wait = time.perf_counter()
    slots.acquire()
    waited = time.perf_counter() - started_wait
    with _stats_lock:
        _waiting -= 1
        _active += 1
        active_now = _active
        waiting_now = _waiting

    logger.info(
        "Render queue start label=%s waited=%.2fs active=%s waiting=%s",
        label,
        waited,
        active_now,
        waiting_now,
    )
    started_run = time.perf_counter()
    try:
        return fn(*args, **kwargs)
    finally:
        elapsed = time.perf_counter() - started_run
        with _stats_lock:
            _active -= 1
            _completed += 1
            active_now = _active
            waiting_now = _waiting
            completed_now = _completed
        slots.release()
        logger.info(
            "Render queue done label=%s elapsed=%.1fs active=%s waiting=%s completed=%s",
            label,
            elapsed,
            active_now,
            waiting_now,
            completed_now,
        )
