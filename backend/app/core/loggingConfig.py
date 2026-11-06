"""Backend log facade — ``backend/logs/{domain}/{service}.log``.

SoT: ``docs/tz_logging.md``. Events (what to emit) stay in domain TZs; this
module only routes records to files. One process writer per file (L1).
Transcript bake files stay in ``generationLogging`` — not these rotating sinks.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TextIO

from app.core.logging import console, fileRouter, formatting, routes


def _is_facade_handler(handler: logging.Handler) -> bool:
    return bool(getattr(handler, "_ai_project_log_facade", False))


def _remove_facade_handlers() -> None:
    """Drop console + domain router. Generation transcript handlers stay."""
    console.stop_console_listener()
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
    profile: str = routes.PROFILE_SERVER,
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
    if profile == routes.PROFILE_SCRIPT:
        script_service = fileRouter._require_service_stem(script_service or "")
    logs_root = Path(logs_dir) if logs_dir is not None else fileRouter.backend_logs_dir()
    logs_root.mkdir(parents=True, exist_ok=True)

    formatter = formatting.JsonLogFormatter()
    console_handler = console.create_console(formatter=formatter, stream=stream or sys.stdout)

    router = fileRouter.DomainFileRouter(
        profile=profile,
        logs_dir=logs_root,
        script_service=script_service,
    )
    router.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    _remove_facade_handlers()

    qh = console.start_console(console_handler)
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
            profile=routes.PROFILE_SCRIPT,
            script_service=service,
            logs_dir=logs_dir,
            stream=stream,
        )
        return
    set_logging_level(level)
