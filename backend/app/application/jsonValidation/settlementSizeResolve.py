"""Runtime resolve of settlement size rank — tz_locations.md LOC-T-2.

Omit / SQL NULL → canonical medium, no warning.
Type fail or key not in this world's registry → medium + json_validation WARNING
(product sink ``jsonValidation`` / ``resolve``, see docs/tz_logging.md).
"""

from __future__ import annotations

import logging
from typing import Any

from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
    SettlementSizeKey,
    WorldSettlementSizeRegistry,
)

logger = logging.getLogger(__name__)

_warned: set[tuple[str, str]] = set()


def resolve_settlement_size_key(
    size_registry: WorldSettlementSizeRegistry,
    raw: Any,
    *,
    world_uid: str = "",
) -> SettlementSizeKey:
    """Return a key present in ``size_registry`` (canonical medium on miss)."""
    default = WorldSettlementSizeRegistry.default_system_size()
    if raw is None:
        return size_registry.resolve_system_size(None)
    if not isinstance(raw, str):
        _warn_fallback(world_uid, raw, default)
        return default
    stripped = raw.strip()
    if not stripped:
        return default
    found = size_registry.entry_for(stripped)
    if found is not None:
        return found.system_size
    _warn_fallback(world_uid, stripped, default)
    return default


def _warn_fallback(world_uid: str, wire: Any, resolved: SettlementSizeKey) -> None:
    token = str(wire)
    key = (world_uid, token)
    if key in _warned:
        return
    _warned.add(key)
    logger.warning(
        "json_validation | settlement_size invalid %r; using field default %r",
        wire,
        resolved,
        extra={
            "activity": "settlement_size_fallback",
            "world_uid": world_uid or None,
            "wire": token,
            "resolved": resolved,
        },
    )
