"""ASCII dump / smoke-script ticks — application logging stack.

SoT: ``app.core.loggingConfig`` (console + ``backend/logs/app.log``) and
``generation_world_log(mode="dump")`` → ``backend/logs/generation/{uid}/bake-dump-*.log``.

Not ``print``, not a script-local tee. Heartbeat ≤5 s (``DEBUG_PROGRESS_POLL_S``).
"""
from __future__ import annotations

import argparse
import logging
import os
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger(__name__)

DEBUG_LOGGING_HELP = "Set root log level to DEBUG (default INFO)"


def heartbeat_s() -> float:
    """Max silence for dump/bake ticks. Gap longer than this is a bug."""
    return float(os.environ.get("DEBUG_PROGRESS_POLL_S", "5"))


def log_dump(msg: str, *, activity: str = "dump", **fields: Any) -> None:
    extra = {"activity": activity, **fields}
    logger.info(msg, extra=extra)


def log_dump_warning(msg: str, *, activity: str = "dump", **fields: Any) -> None:
    extra = {"activity": activity, **fields}
    logger.warning(msg, extra=extra)


def log_dump_kv(title: str, fields: dict[str, Any], *, activity: str = "script") -> None:
    parts = " ".join(f"{k}={v}" for k, v in fields.items())
    log_dump(f"{title} | {parts}", activity=activity)


class DumpProgress:
    """File-count ticks that also fire at least every ``heartbeat_s()``.

    Call ``tick`` after each item; wrap the slow iterator with ``heartbeat_loop``
    so a single item longer than the heartbeat still logs.
    """

    def __init__(
        self,
        label: str,
        *,
        every_n: int = 1,
        activity: str | None = None,
    ) -> None:
        self.label = label
        self.activity = activity or "dump_progress"
        self.every_n = max(1, int(every_n))
        self.t0 = time.monotonic()
        self._last_emit = 0.0
        self.n = 0
        self.extra = ""

    def snapshot_line(self) -> str:
        extra = f" {self.extra}" if self.extra else ""
        return (
            f"{self.label} {self.n}{extra} "
            f"elapsed_s={time.monotonic() - self.t0:.1f}"
        )

    def start(self) -> None:
        self._emit()

    def tick(self, n: int, extra: str = "") -> None:
        self.n = int(n)
        self.extra = extra
        now = time.monotonic()
        due_n = self.n == 1 or self.n % self.every_n == 0
        due_t = (now - self._last_emit) >= heartbeat_s()
        if due_n or due_t:
            self._emit(now)

    def done(self) -> None:
        extra = f" {self.extra}" if self.extra else ""
        log_dump(
            f"{self.label} done: {self.n}{extra} "
            f"elapsed_s={time.monotonic() - self.t0:.1f}",
            activity=self.activity,
            n=self.n,
            elapsed_s=round(time.monotonic() - self.t0, 1),
        )

    def _emit(self, now: float | None = None) -> None:
        self._last_emit = time.monotonic() if now is None else now
        log_dump(
            self.snapshot_line(),
            activity=self.activity,
            n=self.n,
            elapsed_s=round(time.monotonic() - self.t0, 1),
        )


def add_debug_logging_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--debug",
        action="store_true",
        help=DEBUG_LOGGING_HELP,
    )


@contextmanager
def heartbeat_loop(
    sample: Callable[[], str | None],
    *,
    interval_s: float | None = None,
    activity: str = "heartbeat",
) -> Iterator[None]:
    """Call ``sample()`` on an interval; each new line goes through ``log_dump``.

    Use around a blocking bake/HTTP so the generation log ticks while the caller waits.
    """
    interval = float(interval_s if interval_s is not None else heartbeat_s())
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
        log_dump(text, activity=activity)

    def _loop() -> None:
        while not stop.wait(interval):
            try:
                _emit(sample())
            except Exception:
                continue

    thread = threading.Thread(target=_loop, name="dump-heartbeat", daemon=True)
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
