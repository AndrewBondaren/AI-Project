"""Existing nonblocking console queue and its process-owned listener."""
from __future__ import annotations

import logging
import logging.handlers
import queue
import time
from typing import TextIO

# Per-entity bake storms — files + transcript only. Console stays heartbeats.
_CONSOLE_FILE_ONLY_ACTIVITIES = frozenset({
    "grade_cell_empty_ray",
    "grade_system_create",
    "grade_system_members",
    "c22_packing_fit",
    "overlap_rerank_deferred",
})

_CONSOLE_QUEUE_MAX = 4096

_console_queue: queue.Queue[logging.LogRecord | None] | None = None
_console_listener: logging.handlers.QueueListener | None = None
_console_handler: logging.Handler | None = None

class _FacadeStreamHandler(logging.StreamHandler):
    _ai_project_log_facade = True


class _ConsoleVolumeFilter(logging.Filter):
    """Stdout: skip per-cell / per-system bake storms (they stay on file sinks)."""

    def filter(self, record: logging.LogRecord) -> bool:
        activity = getattr(record, "activity", None)
        return activity not in _CONSOLE_FILE_ONLY_ACTIVITIES


class _DropQueueHandler(logging.handlers.QueueHandler):
    """Enqueue for the console listener; never block the bake thread."""

    _ai_project_log_facade = True

    def enqueue(self, record: logging.LogRecord) -> None:
        # ``emit`` already called ``prepare``; do not prepare twice.
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            return


def stop_console_listener() -> None:
    global _console_listener, _console_queue, _console_handler
    listener = _console_listener
    console = _console_handler
    _console_listener = None
    _console_queue = None
    _console_handler = None
    if listener is not None:
        listener.stop()
    if console is not None:
        console.close()


def flush_console_queue(*, timeout_s: float = 2.0) -> None:
    """Wait until the console listener drained the queue (tests)."""
    pending = _console_queue
    if pending is None:
        return
    deadline = time.monotonic() + max(0.05, float(timeout_s))
    while time.monotonic() < deadline:
        if pending.empty():
            time.sleep(0.02)
            if pending.empty():
                return
        time.sleep(0.01)



def create_console(*, formatter: logging.Formatter, stream: TextIO) -> logging.Handler:
    console = _FacadeStreamHandler(stream)
    console.setFormatter(formatter)
    console.addFilter(_ConsoleVolumeFilter())
    return console


def start_console(console: logging.Handler) -> logging.Handler:
    pending: queue.Queue[logging.LogRecord | None] = queue.Queue(
        maxsize=_CONSOLE_QUEUE_MAX,
    )
    qh = _DropQueueHandler(pending)
    qh.addFilter(_ConsoleVolumeFilter())
    listener = logging.handlers.QueueListener(pending, console)
    global _console_queue, _console_listener, _console_handler
    _console_queue = pending
    _console_listener = listener
    _console_handler = console
    listener.start()
    return qh
