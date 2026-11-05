"""Runtime resolve of settlement size rank — tz_locations.md LOC-T-2.

Omit / SQL NULL → canonical medium, no warning.
Type fail or unknown key → unresolved through shared json_validation sink
(product sink ``jsonValidation`` / ``resolve``, see docs/tz_logging.md).
"""

from __future__ import annotations

from typing import Any
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue

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
    # A raw column/condition value, not a field of a validated POJO: F09 at its wire location.
    ctx = ResolveContext(location=WireLocation(parts=("world", world_uid or "?", "system_city_size")))
    if not isinstance(raw, str):
        reject_unresolved(ctx, [WireShapeIssue(code=JsonValidationCode.SCHEMA_VIOLATION, pydantic_type="string_type",
                                               location=ctx.location, message="expected settlement size string")])
    stripped = raw.strip()
    if not stripped:
        return default  # documented blank auto sentinel
    found = size_registry.entry_for(stripped)
    if found is not None:
        return found.system_size
    reject_unresolved(ctx, [WireShapeIssue(code=JsonValidationCode.REF_W_UNKNOWN, location=ctx.location,
                                           message=f"unknown reference: {stripped!r}")])
