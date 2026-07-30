"""Relief logging helpers — tz_terrain_relief R8 + R21/R34 WARNING."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("app.relief")


def relief_info(event: str, **fields: Any) -> None:
    logger.info("relief | %s | %s", event, _fmt(fields))


def relief_warning(event: str, **fields: Any) -> None:
    logger.warning("relief | %s | %s", event, _fmt(fields))


def relief_debug(event: str, **fields: Any) -> None:
    logger.debug("relief | %s | %s", event, _fmt(fields))


def _fmt(fields: dict[str, Any]) -> str:
    return " ".join(f"{k}={v!r}" for k, v in fields.items() if v is not None)
