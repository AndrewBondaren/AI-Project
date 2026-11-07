"""Lazy rotating file delivery and canonical backend log paths."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from app.core.logging import routes
from app.core.logging.contracts import LogSink

_ROTATE_MAX_BYTES = 10 * 1024 * 1024
_ROTATE_BACKUP_COUNT = 5

def backend_logs_dir() -> Path:
    """``backend/logs`` regardless of process cwd."""
    return Path(__file__).resolve().parents[3] / "logs"


def consumer_log_path(
    sink: LogSink,
    *,
    logs_dir: Path | str | None = None,
) -> Path:
    """``{logs_dir}/{domain}/{service}.log``."""
    base = Path(logs_dir) if logs_dir is not None else backend_logs_dir()
    if type(sink) is not LogSink:
        raise TypeError("expected LogSink")
    return base / (sink.value + ".log")


def script_log_path(service: str, *, logs_dir: Path | str | None = None) -> Path:
    base = Path(logs_dir) if logs_dir is not None else backend_logs_dir()
    return base / "script" / (_require_service_stem(service) + ".log")


def _require_service_stem(service: str) -> str:
    stem = (service or "").strip()
    if not stem or "/" in stem or "\\" in stem or stem in {".", ".."}:
        raise ValueError(f"invalid log service stem: {service!r}")
    return stem


class DomainFileRouter(logging.Handler):
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
        if profile not in (routes.PROFILE_SERVER, routes.PROFILE_SCRIPT):
            raise ValueError(f"unknown log profile: {profile!r}")
        if profile == routes.PROFILE_SCRIPT:
            script_service = _require_service_stem(script_service or "")
        self._profile = profile
        self._logs_dir = logs_dir
        self._script_service = script_service
        self._handlers: dict[Path, logging.Handler] = {}

    def _paths_for(self, record: logging.LogRecord) -> tuple[Path, ...]:
        route = routes.route_for(record.name)
        if self._profile == routes.PROFILE_SCRIPT:
            assert self._script_service is not None
            path = script_log_path(self._script_service, logs_dir=self._logs_dir)
            if route.sink is LogSink.RENDER_DUMP:
                return path, consumer_log_path(route.sink, logs_dir=self._logs_dir)
            return (path,)
        if route.server_enabled:
            return (consumer_log_path(route.sink, logs_dir=self._logs_dir),)
        return ()

    def _handler_for(self, path: Path) -> logging.Handler:
        handler = self._handlers.get(path)
        if handler is not None:
            return handler
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=_ROTATE_MAX_BYTES,
            backupCount=_ROTATE_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(self.formatter)
        handler.setLevel(logging.NOTSET)
        self._handlers[path] = handler
        return handler

    def emit(self, record: logging.LogRecord) -> None:
        paths = self._paths_for(record)
        try:
            for path in paths:
                self._handler_for(path).handle(record)
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
