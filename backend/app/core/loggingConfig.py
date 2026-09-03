"""Backend log facade — ``backend/logs/{domain}/{service}.log``.

SoT: ``docs/tz_logging.md``. Events (what to emit) stay in domain TZs; this
module only routes records to files. One process writer per file (L1).
Transcript bake files stay in ``generationLogging`` — not these rotating sinks.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import queue
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_RECORD_BUILTINS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName", "process",
    "processName", "message", "asctime", "taskName",
})

_ROTATE_MAX_BYTES = 10 * 1024 * 1024
_ROTATE_BACKUP_COUNT = 5

# R44 activity on ``app.relief`` (event name from relief log helpers, not imported).
_R44_ACTIVITY = "grade_cell_empty_ray"

# Per-entity bake storms — files + transcript only. Console stays heartbeats.
_CONSOLE_FILE_ONLY_ACTIVITIES = frozenset({
    "grade_cell_empty_ray",
    "grade_system_create",
    "grade_system_members",
    "c22_packing_fit",
})

_CONSOLE_QUEUE_MAX = 4096

_console_queue: queue.Queue[logging.LogRecord | None] | None = None
_console_listener: logging.handlers.QueueListener | None = None
_console_handler: logging.Handler | None = None

PROFILE_SERVER = "server"
PROFILE_SCRIPT = "script"

# Longest prefix first. ``app.relief`` is handled in route_for (R44 split).
_PREFIX_ROUTES: tuple[tuple[str, str, str], ...] = tuple(
    sorted(
        (
            (
                "app.application.worldData.pack.bake.packDetailedBakeOrchestrator",
                "pack",
                "packDetailedBake",
            ),
            (
                "app.application.worldData.pack.bake.packBakeLog",
                "pack",
                "packBakeLog",
            ),
            (
                "app.application.worldData.pack.refine",
                "pack",
                "fineChunkPersist",
            ),
            (
                "app.application.worldData.render.dumpLog",
                "render",
                "dumpLog",
            ),
            (
                "app.application.worldData.terrainParallelLog",
                "terrain",
                "terrainParallelLog",
            ),
            (
                "app.application.worldData.generators.assemblers.climateAssembler",
                "climate",
                "climateLog",
            ),
            (
                "app.application.worldData.generators.assemblers",
                "settlement",
                "settlementAssembler",
            ),
            (
                "app.application.worldData.generators.climate",
                "climate",
                "climateLog",
            ),
            ("http", "http", "api"),
        ),
        key=lambda row: len(row[0]),
        reverse=True,
    )
)

# Server profile allowlist — catalog process=server plus unmatched sink.
# Do not include script/* or render/dumpLog (script-only).
SERVER_SINKS: frozenset[tuple[str, str]] = frozenset({
    ("http", "api"),
    ("pack", "packBakeLog"),
    ("pack", "packDetailedBake"),
    ("pack", "fineChunkPersist"),
    ("relief", "reliefLog"),
    ("relief", "gradeCellRays"),
    ("terrain", "terrainParallelLog"),
    ("climate", "climateLog"),
    ("settlement", "settlementAssembler"),
    ("structure", "headroom"),
    ("core", "runtime"),
})

_DUMP_SINK = ("render", "dumpLog")
_RUNTIME_SINK = ("core", "runtime")


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line — domain files and generation transcript."""

    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "msg": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key not in _RECORD_BUILTINS and not key.startswith("_"):
                obj[key] = val
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)


# Back-compat alias
_JsonFormatter = JsonLogFormatter


def backend_logs_dir() -> Path:
    """``backend/logs`` regardless of process cwd."""
    return Path(__file__).resolve().parents[2] / "logs"


def consumer_log_path(
    domain: str,
    service: str,
    *,
    logs_dir: Path | str | None = None,
) -> Path:
    """``{logs_dir}/{domain}/{service}.log``."""
    base = Path(logs_dir) if logs_dir is not None else backend_logs_dir()
    return base / domain / f"{service}.log"


def _matches_prefix(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def route_for(logger_name: str, activity: object | None = None) -> tuple[str, str] | None:
    """Map logger name (+ optional ``activity`` extra) to ``(domain, service)``.

    Unmatched names return ``None`` (server profile then uses ``core/runtime``).
    """
    name = logger_name or ""
    if _matches_prefix(name, "app.relief"):
        if activity == _R44_ACTIVITY:
            return ("relief", "gradeCellRays")
        return ("relief", "reliefLog")
    for prefix, domain, service in _PREFIX_ROUTES:
        if _matches_prefix(name, prefix):
            return (domain, service)
    return None


def _require_service_stem(service: str) -> str:
    stem = (service or "").strip()
    if not stem or "/" in stem or "\\" in stem or stem in {".", ".."}:
        raise ValueError(f"invalid log service stem: {service!r}")
    return stem


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


class _DomainFileRouter(logging.Handler):
    """Lazy ``RotatingFileHandler`` per ``(domain, service)`` for this process."""

    _ai_project_log_facade = True

    def __init__(
        self,
        *,
        profile: str,
        logs_dir: Path,
        script_service: str | None = None,
    ) -> None:
        super().__init__()
        if profile not in (PROFILE_SERVER, PROFILE_SCRIPT):
            raise ValueError(f"unknown log profile: {profile!r}")
        if profile == PROFILE_SCRIPT:
            script_service = _require_service_stem(script_service or "")
        self._profile = profile
        self._logs_dir = logs_dir
        self._script_service = script_service
        self._handlers: dict[tuple[str, str], logging.Handler] = {}

    def _keys_for(self, record: logging.LogRecord) -> list[tuple[str, str]]:
        routed = route_for(record.name, getattr(record, "activity", None))
        if self._profile == PROFILE_SCRIPT:
            keys: list[tuple[str, str]] = [
                ("script", self._script_service or "script"),
            ]
            if routed == _DUMP_SINK:
                keys.append(_DUMP_SINK)
            return keys
        if routed is None:
            return [_RUNTIME_SINK]
        if routed not in SERVER_SINKS:
            return []
        return [routed]

    def _handler_for(self, key: tuple[str, str]) -> logging.Handler:
        handler = self._handlers.get(key)
        if handler is not None:
            return handler
        domain, service = key
        path = consumer_log_path(domain, service, logs_dir=self._logs_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=_ROTATE_MAX_BYTES,
            backupCount=_ROTATE_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(self.formatter)
        handler.setLevel(logging.NOTSET)
        self._handlers[key] = handler
        return handler

    def emit(self, record: logging.LogRecord) -> None:
        try:
            for key in self._keys_for(record):
                self._handler_for(key).handle(record)
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        self.acquire()
        try:
            for handler in self._handlers.values():
                handler.flush()
        finally:
            self.release()

    def close(self) -> None:
        self.acquire()
        try:
            for handler in self._handlers.values():
                handler.close()
            self._handlers.clear()
        finally:
            self.release()
        super().close()


def _is_facade_handler(handler: logging.Handler) -> bool:
    return bool(getattr(handler, "_ai_project_log_facade", False))


def _stop_console_listener() -> None:
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


def _remove_facade_handlers() -> None:
    """Drop console + domain router. Generation transcript handlers stay."""
    _stop_console_listener()
    root = logging.getLogger()
    for handler in list(root.handlers):
        if _is_facade_handler(handler):
            root.removeHandler(handler)
            handler.close()


def _has_facade_handlers() -> bool:
    return any(_is_facade_handler(h) for h in logging.getLogger().handlers)


def set_logging_level(level: int) -> None:
    """Change root level only — do not replace handlers or open ``app.log``."""
    logging.getLogger().setLevel(level)


def setup_logging(
    *,
    level: int = logging.INFO,
    logger_levels: dict[str, str] | None = None,
    profile: str = PROFILE_SERVER,
    script_service: str | None = None,
    logs_dir: Path | str | None = None,
    stream: TextIO | None = None,
) -> None:
    """Install process console + domain file router.

    Replaces previous facade handlers; leaves ``generation_world_log`` sinks.
    Server profile does not open ``script/*`` or ``render/dumpLog``.
    Console is a drop-queue (does not block the emitter). High-volume
    activities are file + transcript only.
    """
    if profile == PROFILE_SCRIPT:
        script_service = _require_service_stem(script_service or "")
    logs_root = Path(logs_dir) if logs_dir is not None else backend_logs_dir()
    logs_root.mkdir(parents=True, exist_ok=True)

    formatter = JsonLogFormatter()
    console = _FacadeStreamHandler(stream or sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(_ConsoleVolumeFilter())

    router = _DomainFileRouter(
        profile=profile,
        logs_dir=logs_root,
        script_service=script_service,
    )
    router.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    _remove_facade_handlers()

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
    # Files first (sync). Console is a drop-queue so a full stdout pipe
    # cannot stall the bake thread — listener may block, emitter must not.
    root.addHandler(router)
    root.addHandler(qh)

    for name, lvl in (logger_levels or {}).items():
        logging.getLogger(name).setLevel(lvl)


def ensure_script_logging(
    *,
    service: str,
    debug: bool = False,
    logs_dir: Path | str | None = None,
    stream: TextIO | None = None,
) -> None:
    """Console + ``logs/script/{service}.log``; dump also ``logs/render/dumpLog.log``.

    Does not open ``app.log``, ``relief/*``, or ``pack/*``. If facade handlers
    already exist (tests / nested calls), only the root level is updated.
    """
    level = logging.DEBUG if debug else logging.INFO
    if not _has_facade_handlers():
        setup_logging(
            level=level,
            profile=PROFILE_SCRIPT,
            script_service=service,
            logs_dir=logs_dir,
            stream=stream,
        )
        return
    set_logging_level(level)
