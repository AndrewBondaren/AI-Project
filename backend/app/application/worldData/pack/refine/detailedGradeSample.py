"""Sample relief ribbon sites on meter grid — R36u detailed geometry."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.openLandTerrains import (
    open_land_terrain_keys,
)
from app.application.worldData.generators.terrain.relief.ribbonSiteSample import (
    sample_downhill_land_sites,
    sample_landward_of_refs,
)
from app.application.worldData.pack.refine.meterGradeSurface import (
    Coord,
    MeterGradeSurface,
    meter_seed_blocked,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.db.models.world import World

SampleCell = tuple[Coord, str, int]


def sample_open_land_meter(
    surface: MeterGradeSurface,
    *,
    road_key: str,
    world: World | None = None,
) -> tuple[list[SampleCell], set[Coord]]:
    """Uphill land = ref; downhill ortho neighbor = seed."""
    land_terrains = open_land_terrain_keys(world)
    land: dict[Coord, tuple[str, int]] = {}
    for xy, z in surface.surface_z.items():
        terrain = surface.terrain_at(xy)
        if terrain not in land_terrains:
            continue
        if meter_seed_blocked(surface, xy, road_key=road_key):
            continue
        land[xy] = (str(terrain), int(z))
    return sample_downhill_land_sites(land)


def sample_shore_meter(
    surface: MeterGradeSurface,
    *,
    road_key: str,
    world: World | None = None,
) -> tuple[list[SampleCell], set[Coord]]:
    """SHORE hydro role = ref; landward ortho neighbor = seed."""
    if not surface.hydrology:
        return [], set()

    shore_refs: list[tuple[Coord, int]] = []
    for xy, z in surface.surface_z.items():
        if surface.hydro_role_at(xy) is not HydrologyCellRole.SHORE:
            continue
        shore_refs.append((xy, int(z)))

    def neighbor_site(seed: Coord) -> tuple[str, int] | None:
        if seed not in surface.surface_z:
            return None
        if meter_seed_blocked(surface, seed, road_key=road_key):
            return None
        if surface.hydro_role_at(seed) is HydrologyCellRole.SHORE:
            return None
        terrain_lo = surface.terrain_at(seed)
        z_lo = surface.z_at(seed)
        if not terrain_lo or z_lo is None:
            return None
        return str(terrain_lo), int(z_lo)

    return sample_landward_of_refs(shore_refs, neighbor_site=neighbor_site)
