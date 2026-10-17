"""Read-only hydro index for the future wilderness manifest adapter (step 8)."""

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import SurfaceTerrainContext
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.spatial.regionShape import Point
from app.ids.regionIdentity import region_uid


class HydroIndexStatus(StrEnum):
    DECLARED = "declared"
    OBSERVED = "observed"


@dataclass(frozen=True)
class HydroRegionIndexEntry:
    status: HydroIndexStatus
    region_uid: str | None
    location_uid: str | None
    role: HydrologyCellRole | None
    # Observed coordinates remain macro cells, not invented fine footprints.
    macro_cells: frozenset[Point] = frozenset()


def index_hydrology(world_uid: str, hydrology: WorldHydrology,
                    surface: SurfaceTerrainContext | None) -> tuple[HydroRegionIndexEntry, ...]:
    locations = {entry.location_uid for entry in (
        *hydrology.declared_lakes, *hydrology.declared_coastlines, *hydrology.declared_rivers,
    )}
    entries = [HydroRegionIndexEntry(HydroIndexStatus.DECLARED,
                                    region_uid(world_uid, anchor_uid=uid), uid, None)
               for uid in sorted(locations)]
    roles = defaultdict(set)
    if surface is not None:
        for coord, value in surface.coarse_hydro.items():
            if isinstance(value, MapCellHydrology) and value.role is not None:
                roles[value.role].add(coord)
    # The current cell metadata has no owning water-body UID: never guess a link
    # between these observations and declared objects merely from their role.
    entries.extend(HydroRegionIndexEntry(HydroIndexStatus.OBSERVED, None, None, role, frozenset(cells))
                   for role, cells in sorted(roles.items()))
    return tuple(entries)
