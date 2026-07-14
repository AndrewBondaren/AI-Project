"""Per-world generation logs under ``logs/generation/{world_uid}/``.

Separated from ``logs/app.log`` / console so bake diagnostics (surface
context, world_map sampling, tile flat) survive terminal scrollback.

Usage::

    with generation_world_log(world_uid, mode="light") as log_path:
        ...  # pack bake / refine

See ``docs/tz_world_pack_storage.md`` (pack bake diagnostics).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.core.loggingConfig import JsonLogFormatter

# Active bake/refine world for this asyncio Task / thread.
generation_world_var: ContextVar[str | None] = ContextVar("generation_world", default=None)

# Logger name prefixes captured into the generation file (not HTTP/chat).
_GENERATION_PREFIXES: tuple[str, ...] = (
    "app.application.worldData.pack",
    "app.application.worldData.generators",
    "app.application.worldData.terrainBatchOrchestrator",
    "app.application.worldData.terrainParallelLog",
    "app.application.worldData.loadingProgress",
    "app.application.worldData.worldSurfaceMaterializationOrchestrator",
    "app.core.generationLogging",
)

_log = logging.getLogger(__name__)


def generation_log_dir(world_uid: str, *, root: str | Path = "logs/generation") -> Path:
    """``logs/generation/{world_uid}/`` (cwd-relative; normally ``backend/``)."""
    return Path(root) / world_uid


def _stamp_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class _GenerationScopeFilter(logging.Filter):
    """Pass only records for this world's generation scope + allowlisted loggers."""

    def __init__(self, world_uid: str, prefixes: tuple[str, ...] = _GENERATION_PREFIXES) -> None:
        super().__init__()
        self._world_uid = world_uid
        self._prefixes = prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        if generation_world_var.get() != self._world_uid:
            return False
        name = record.name
        return any(name == p or name.startswith(p + ".") for p in self._prefixes)


@contextmanager
def generation_world_log(
    world_uid: str,
    *,
    mode: str,
    root: str | Path = "logs/generation",
    level: int = logging.DEBUG,
) -> Iterator[Path]:
    """Attach a JSON file handler for one generation run; detach on exit.

    Writes:
    - ``bake-{mode}-{stamp}.log`` — immutable run artifact
    - ``bake-{mode}-latest.log`` — same run, overwritten each bake for quick open
    """
    uid = (world_uid or "").strip()
    if not uid:
        raise ValueError("world_uid required for generation_world_log")
    mode_key = (mode or "light").strip().lower() or "light"
    stamp = _stamp_utc()
    out_dir = generation_log_dir(uid, root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_path = out_dir / f"bake-{mode_key}-{stamp}.log"
    latest_path = out_dir / f"bake-{mode_key}-latest.log"

    formatter = JsonLogFormatter()
    filt = _GenerationScopeFilter(uid)

    handlers: list[logging.Handler] = []
    for path in (run_path, latest_path):
        # latest: truncate; stamped: new file
        fh = logging.FileHandler(path, mode="w", encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(formatter)
        fh.addFilter(filt)
        handlers.append(fh)

    root_logger = logging.getLogger()
    token = generation_world_var.set(uid)
    for h in handlers:
        root_logger.addHandler(h)
    try:
        _log.info(
            "generation log open | world=%s mode=%s path=%s latest=%s",
            uid,
            mode_key,
            run_path.as_posix(),
            latest_path.as_posix(),
            extra={"world_uid": uid, "pack_mode": mode_key, "activity": "generation_log_open"},
        )
        yield run_path
    finally:
        _log.info(
            "generation log close | world=%s mode=%s path=%s",
            uid,
            mode_key,
            run_path.as_posix(),
            extra={"world_uid": uid, "pack_mode": mode_key, "activity": "generation_log_close"},
        )
        for h in handlers:
            root_logger.removeHandler(h)
            h.close()
        generation_world_var.reset(token)
