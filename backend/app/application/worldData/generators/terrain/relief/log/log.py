"""Relief logging helpers — tz_terrain_relief R8 + R21/R34 WARNING + R44 ERROR."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.core.logging.contracts import LogConsumer
from app.core.logging.consumers import get_consumer_logger
from app.application.worldData.materialize.terrain.terrainParallelLog import current_cpu_core
from app.application.worldData.generators.terrain.relief.log.events import EVENT_GRADE_CELL_EMPTY_RAY

_relief_logger = get_consumer_logger(LogConsumer.RELIEF)
_rays_logger = get_consumer_logger(LogConsumer.RELIEF_RAYS)


def _event_logger(event: str) -> logging.Logger:
    if event == EVENT_GRADE_CELL_EMPTY_RAY:
        return _rays_logger
    return _relief_logger


def _worker_fields() -> dict[str, Any]:
    thread = threading.current_thread()
    return {
        "cpu_core": current_cpu_core(),
        "worker_thread": thread.name,
        "worker_tid": thread.ident,
    }


def _extra(event: str, worker: dict[str, Any]) -> dict[str, Any]:
    return {"activity": event, **worker}


def relief_info(event: str, **fields: Any) -> None:
    worker = _worker_fields()
    _event_logger(event).info("relief | %s | %s", event, _fmt(fields), extra=_extra(event, worker))


def relief_warning(event: str, **fields: Any) -> None:
    worker = _worker_fields()
    _event_logger(event).warning("relief | %s | %s", event, _fmt(fields), extra=_extra(event, worker))


def relief_error(event: str, **fields: Any) -> None:
    worker = _worker_fields()
    _event_logger(event).error("relief | %s | %s", event, _fmt(fields), extra=_extra(event, worker))


def relief_debug(event: str, **fields: Any) -> None:
    worker = _worker_fields()
    _event_logger(event).debug(
        "relief | %s | %s",
        event,
        _fmt({**fields, **worker}),
        extra=_extra(event, worker),
    )


def _fmt(fields: dict[str, Any]) -> str:
    return " ".join(f"{k}={v!r}" for k, v in fields.items() if v is not None)
