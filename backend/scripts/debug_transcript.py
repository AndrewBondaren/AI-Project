"""Smoke-script transcript: one place for print vs file.

``print()`` inside ``tee_stdio`` → real terminal **and** the log file.
``progress()`` → log file always (nested tees too); terminal only if
``set_debug_progress(True)`` or ``DEBUG_PROGRESS=1``.

Use for long bake/render heartbeats so the process is watchable without
flooding the terminal, and the full tick stream is not lost to scrollback.

Consumers: ``detailed_bake``, ``light_and_full_bake``, ``entry_bg_refine``,
``render_maps``, ``initialize_world``.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

_DEBUG_PROGRESS = False

DEBUG_PROGRESS_HELP = (
    "Heartbeat ticks on the terminal; always written to the transcript file "
    "(or DEBUG_PROGRESS=1)"
)


class TeeStream:
    """Mirror writes to a primary stream and a log file; flush every write."""

    def __init__(self, primary: TextIO, log_file: TextIO) -> None:
        self._primary = primary
        self._log = log_file

    def write(self, data: str) -> int:
        self._primary.write(data)
        self._log.write(data)
        self._primary.flush()
        self._log.flush()
        return len(data)

    def flush(self) -> None:
        self._primary.flush()
        self._log.flush()

    def write_log_only(self, data: str) -> None:
        """File (+ nested tee logs); not the real terminal."""
        self._log.write(data)
        self._log.flush()
        chained = getattr(self._primary, "write_log_only", None)
        if callable(chained):
            chained(data)

    def reconfigure(self, **kwargs: object) -> None:
        reconf = getattr(self._primary, "reconfigure", None)
        if callable(reconf):
            reconf(**kwargs)


def set_debug_progress(enabled: bool) -> None:
    """Terminal heartbeat on/off. File ticks do not depend on this."""
    global _DEBUG_PROGRESS
    _DEBUG_PROGRESS = bool(enabled)


def debug_progress_enabled() -> bool:
    if _DEBUG_PROGRESS:
        return True
    raw = os.environ.get("DEBUG_PROGRESS", "").strip().lower()
    return raw in ("1", "true", "yes")


def progress(msg: str) -> None:
    """Heartbeat line: transcript file always; stdout only when debug progress is on."""
    line = msg if msg.endswith("\n") else f"{msg}\n"
    if debug_progress_enabled():
        print(msg, flush=True)
        return
    write_log_only = getattr(sys.stdout, "write_log_only", None)
    if callable(write_log_only):
        write_log_only(line)


def add_debug_progress_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--debug",
        action="store_true",
        help=DEBUG_PROGRESS_HELP,
    )


@contextmanager
def progress_loop(
    sample: Callable[[], str | None],
    *,
    interval_s: float | None = None,
) -> Iterator[None]:
    """Call ``sample()`` on an interval; each new line goes through ``progress()``.

    Use around a blocking bake/HTTP so the transcript ticks while the caller waits.
    """
    interval = float(
        interval_s
        if interval_s is not None
        else os.environ.get("DEBUG_PROGRESS_POLL_S", "5")
    )
    stop = threading.Event()
    last: str | None = None

    def _emit(line: str | None, *, suffix: str = "") -> None:
        nonlocal last
        if not line:
            return
        text = f"{line} {suffix}".rstrip() if suffix else line
        if text == last:
            return
        last = text
        progress(text)

    def _loop() -> None:
        while not stop.wait(interval):
            try:
                _emit(sample())
            except Exception:
                continue

    thread = threading.Thread(target=_loop, name="script-progress-loop", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=interval + 1.0)
        try:
            _emit(sample(), suffix="(final)")
        except Exception:
            pass


@contextmanager
def tee_stdio(log_path: Path, *, announce_saved: bool = False) -> Iterator[Path]:
    """Replace stdout/stderr with tees into ``log_path`` for the block."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8", newline="\n")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = TeeStream(old_out, log_file)  # type: ignore[assignment]
    sys.stderr = TeeStream(old_err, log_file)  # type: ignore[assignment]
    try:
        yield log_path
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
        log_file.flush()
        log_file.close()
        if announce_saved:
            print(f"\nfull transcript saved: {log_path}", file=old_out, flush=True)
