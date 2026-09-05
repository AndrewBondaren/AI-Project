"""C6 target filter + C14 skip: file + manifest + SQL children."""

from __future__ import annotations

from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.dataModel.locations.locationFootprintPolicy import (
    named_location_is_settlement_map_site,
)
from app.db.models.namedLocation import NamedLocation
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository


def is_settlement_outdoor_target(location: NamedLocation) -> bool:
    """C6: settlement-like footprint, not district/building descendants."""
    return named_location_is_settlement_map_site(location)


async def should_skip_materialize(
    settlement: NamedLocation,
    writer: WorldPackWriter,
    location_repo: INamedLocationRepository,
) -> bool:
    if not writer.has_published_settlement(settlement.location_uid):
        return False
    children = await location_repo.get_children(settlement.location_uid)
    return bool(children)
