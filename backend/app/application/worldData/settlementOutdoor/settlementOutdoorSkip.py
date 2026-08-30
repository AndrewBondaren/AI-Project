"""C6 target filter + C14 skip: file + manifest + SQL children."""

from __future__ import annotations

from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.dataModel.locations.locationFootprintPolicy import (
    named_location_uses_settlement_meter_footprint,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.db.models.namedLocation import NamedLocation
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository


def is_settlement_outdoor_target(location: NamedLocation) -> bool:
    """C6: settlement-like footprint, not district/building descendants."""
    if not named_location_uses_settlement_meter_footprint(location):
        return False
    loc_type = (location.system_location_type or "").strip().lower()
    entry = WorldLocationTypeRegistry.canonical_engine().entry_for(loc_type)
    if entry is None:
        return True
    settlement = WorldLocationTypeRegistry.canonical_engine().entry_for("settlement")
    if settlement is not None and entry.system_type == settlement.system_type:
        return True
    parents = entry.parent_types or []
    nested_under = {
        e.system_type
        for key in ("settlement", "district", "building")
        if (e := WorldLocationTypeRegistry.canonical_engine().entry_for(key)) is not None
    }
    return not any(p in nested_under for p in parents if p)


async def should_skip_materialize(
    settlement: NamedLocation,
    writer: WorldPackWriter,
    location_repo: INamedLocationRepository,
) -> bool:
    if not writer.has_published_settlement(settlement.location_uid):
        return False
    children = await location_repo.get_children(settlement.location_uid)
    return bool(children)
