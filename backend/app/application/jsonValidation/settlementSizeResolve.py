"""Runtime resolve of settlement size rank — tz_locations.md LOC-T-2.

Omit / SQL NULL → canonical medium, no warning.
Type fail or unknown key → unresolved through shared json_validation sink
(product sink ``jsonValidation`` / ``resolve``, see docs/tz_logging.md).
"""

from __future__ import annotations

from typing import Any
from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved
from app.application.jsonValidation.types import FieldPathError

from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import (
    SettlementSizeKey,
    WorldSettlementSizeRegistry,
)

def resolve_settlement_size_key(
    size_registry: WorldSettlementSizeRegistry,
    raw: Any,
    *,
    world_uid: str = "",
) -> SettlementSizeKey:
    """Return a key present in ``size_registry`` (canonical medium only for ordinary absence)."""
    default = WorldSettlementSizeRegistry.default_system_size()
    if raw is None:
        return size_registry.resolve_system_size(None)
    ctx = ResolveContext(path_prefix=("world", world_uid or "?", "system_city_size"))
    if not isinstance(raw, str):
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, "expected settlement size string", code="string_type")])
    stripped = raw.strip()
    if not stripped:
        return default  # documented blank auto sentinel
    found = size_registry.entry_for(stripped)
    if found is not None:
        return found.system_size
    reject_unresolved(ctx, [FieldPathError(ctx.path_prefix, f"unknown reference: {stripped!r}", code="REF_W_UNKNOWN")])
