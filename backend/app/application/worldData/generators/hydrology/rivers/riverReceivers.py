"""Read confirmed drainage; a foreign bed is a receiver only at confluence."""

from collections.abc import Mapping, Sequence

from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink, RiverReceiverKind
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.topology.worldTopology import Coord


def drainage_index(occupied: Mapping[Coord, MapCellHydrology]) -> dict[str, RiverDrainageLink]:
    return {entry.river_drainage.river_uid: entry.river_drainage
            for entry in occupied.values() if entry.river_drainage is not None}


def drains_to_basin(uid: str, links: Mapping[str, RiverDrainageLink], *, excluding: str) -> bool:
    """Require a finite proven chain; unknown metadata never implies connectivity."""
    seen = {excluding}
    while uid not in seen:
        seen.add(uid)
        link = links.get(uid)
        if link is None or link.receiver_uid in seen:
            return False
        if isinstance(link.receiver_kind, BasinKind):
            return True
        uid = link.receiver_uid
    return False


def receiver_kind(cell: Coord, occupied: Mapping[Coord, MapCellHydrology],
                  bodies: Sequence[WaterBody]) -> RiverReceiverKind | None:
    entry = occupied[cell]
    if entry.role is Role.RIVER_BED:
        return entry.river_drainage.river_type if entry.river_drainage is not None else None
    for body in bodies:
        if body.water_body_uid == entry.water_body_uid:
            return body.kind
    return {Role.COASTAL_SEA: BasinKind.SEA, Role.OPEN_OCEAN: BasinKind.OCEAN,
            Role.INLAND_SEA: BasinKind.INLAND_SEA, Role.LAKE: BasinKind.LAKE}.get(entry.role)
