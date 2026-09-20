"""C6 target filter + C14 skip: packed set / complete, not SQL children."""

from __future__ import annotations

from collections.abc import Sequence

from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    has_authored_non_district_children,
)
from app.dataModel.locations.locationFootprintPolicy import (
    named_location_is_settlement_map_site,
)
from app.dataModel.worldPack.worldPackManifest import SettlementStructureEntry
from app.db.models.namedLocation import NamedLocation
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository


def is_settlement_outdoor_target(location: NamedLocation) -> bool:
    """C6: settlement-like footprint, not district/building descendants."""
    return named_location_is_settlement_map_site(location)


def packing_queue(
    census: list[NamedLocation],
    packed: Sequence[str],
) -> list[NamedLocation]:
    packed_set = set(packed)
    return [row for row in census if row.location_uid not in packed_set]


def _structure_entry(
    writer: WorldPackWriter, location_uid: str,
) -> SettlementStructureEntry | None:
    if not writer.has_published_settlement(location_uid):
        return None
    entry = writer.manifest.settlement_structure_entry(location_uid)
    if not isinstance(entry, SettlementStructureEntry):
        return None
    return entry


def packed_district_uids(writer: WorldPackWriter, location_uid: str) -> list[str]:
    entry = _structure_entry(writer, location_uid)
    if entry is None:
        return []
    return list(entry.packed_district_uids)


async def should_skip_materialize(
    settlement: NamedLocation,
    writer: WorldPackWriter,
    location_repo: INamedLocationRepository,
    *,
    district_uid: str | None = None,
    children: list[NamedLocation] | None = None,
) -> bool:
    rows = (
        children
        if children is not None
        else await location_repo.get_children(settlement.location_uid)
    )
    if has_authored_non_district_children(rows):
        return True
    entry = _structure_entry(writer, settlement.location_uid)
    if entry is None:
        return False
    if district_uid is not None:
        return district_uid in entry.packed_district_uids
    return entry.structure_status == "complete"
