"""Relief logging helpers — tz_terrain_relief R8 + R21/R34 WARNING."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.application.worldData.terrainParallelLog import current_cpu_core

logger = logging.getLogger("app.relief")


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
    logger.info("relief | %s | %s", event, _fmt(fields), extra=_extra(event, worker))


def relief_warning(event: str, **fields: Any) -> None:
    worker = _worker_fields()
    logger.warning("relief | %s | %s", event, _fmt(fields), extra=_extra(event, worker))


def relief_debug(event: str, **fields: Any) -> None:
    worker = _worker_fields()
    logger.debug(
        "relief | %s | %s",
        event,
        _fmt({**fields, **worker}),
        extra=_extra(event, worker),
    )


def _fmt(fields: dict[str, Any]) -> str:
    return " ".join(f"{k}={v!r}" for k, v in fields.items() if v is not None)
