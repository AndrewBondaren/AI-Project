"""Shared plumbing for ``pack.bake.log`` phase modules — one logger, one extra builder."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from app.application.worldData.materialize.terrainParallelLog import current_cpu_core

# Historical name kept verbatim: loggingConfig routes this prefix to the
# ``pack/packBakeLog`` sink and tests attach to this exact logger.
logger = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")


def _async_task_name() -> str:
    try:
        task = asyncio.current_task()
        return task.get_name() if task is not None else "-"
    except RuntimeError:
        return "-"


def _diag_extra(
    *,
    activity: str,
    pool_workers: int | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Structured fields for JSON logs — thread / CPU / activity as top-level keys."""
    thread = threading.current_thread()
    extra: dict[str, Any] = {
        "activity": activity,
        "worker_thread": thread.name,
        "worker_tid": thread.ident,
        "cpu_core": current_cpu_core(),
        "asyncio_task": _async_task_name(),
    }
    if pool_workers is not None:
        extra["pool_workers"] = pool_workers
    extra.update(fields)
    return extra


def _info(msg: str, *args: Any, activity: str, pool_workers: int | None = None, **fields: Any) -> None:
    logger.info(msg, *args, extra=_diag_extra(activity=activity, pool_workers=pool_workers, **fields))


def _error(msg: str, *args: Any, activity: str, pool_workers: int | None = None, **fields: Any) -> None:
    logger.error(msg, *args, extra=_diag_extra(activity=activity, pool_workers=pool_workers, **fields))


def _debug(msg: str, *args: Any, activity: str, pool_workers: int | None = None, **fields: Any) -> None:
    logger.debug(msg, *args, extra=_diag_extra(activity=activity, pool_workers=pool_workers, **fields))
