"""Sample relief ribbon sites on detailed geometry — R36u / R36v rect-scoped."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.geom.facing import CARDINAL_ORTHO_DELTAS
from app.application.worldData.generators.terrain.relief.sample.openLandTerrains import (
    open_land_terrain_keys,
)
from app.application.worldData.generators.terrain.relief.sample.ravineTerrain import (
    ravine_terrain_key,
)
from app.application.worldData.generators.terrain.relief.sample.ribbonSiteSample import (
    SampleCell,
    sample_downhill_land_sites,
    sample_landward_of_refs,
)
from app.application.worldData.generators.terrain.relief.geom.outward import has_relief_dz
from app.application.worldData.pack.refine.columnBounds import (
    ColumnBounds,
    expand_rect,
    rect_contains,
)
from app.application.worldData.pack.refine.meterGradeSurface import (
    Coord,
    MeterGradeSurface,
    meter_seed_blocked,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.db.models.world import World


def _iter_z_in_bounds(
    surface: MeterGradeSurface,
    bounds: ColumnBounds,
):
    for y in range(bounds.y_min, bounds.y_max + 1):
        for x in range(bounds.x_min, bounds.x_max + 1):
            xy = (x, y)
            z = surface.z_at(xy)
            if z is None:
                continue
            yield xy, z


def _sample_bounds(
    rect: ColumnBounds | None,
    halo: int,
) -> ColumnBounds | None:
    if rect is None:
        return None
    return expand_rect(rect, halo)


def _keep_owned_seeds(
    samples: list[SampleCell],
    rect: ColumnBounds | None,
) -> list[SampleCell]:
    if rect is None:
        return samples
    return [
        item for item in samples
        if rect_contains(rect, item.xy[0], item.xy[1])
    ]


def _refs_for_owned_seeds(
    refs: set[Coord],
    samples: list[SampleCell],
) -> set[Coord]:
    """Keep halo/crest refs of owned seeds; never a seed (R36t / cascade)."""
    owned = {item.xy for item in samples}
    keep: set[Coord] = set()
    for rx, ry in refs:
        if (rx, ry) in owned:
            continue
        for dx, dy in CARDINAL_ORTHO_DELTAS:
            if (rx + dx, ry + dy) in owned:
                keep.add((rx, ry))
                break
    return keep


def sample_open_land_meter(
    surface: MeterGradeSurface,
    *,
    road_key: str,
    world: World | None = None,
    rect: ColumnBounds | None = None,
    halo: int = 0,
) -> tuple[list[SampleCell], set[Coord]]:
    """Uphill land = ref; downhill ortho neighbor = seed.

    ``rect`` + ``halo``: scan only bounds; emit seeds with ``seed ∈ rect`` (R36v).
    """
    land_terrains = open_land_terrain_keys(world)
    land: dict[Coord, tuple[str, int]] = {}
    bounds = _sample_bounds(rect, halo)
    cells = (
        _iter_z_in_bounds(surface, bounds)
        if bounds is not None
        else surface.surface_z.items()
    )
    for xy, z in cells:
        terrain = surface.terrain_at(xy)
        if terrain not in land_terrains:
            continue
        if meter_seed_blocked(surface, xy, road_key=road_key, ignore_grade=True):
            continue
        land[xy] = (str(terrain), int(z))
    samples, refs = sample_downhill_land_sites(land)
    samples = [
        item for item in samples
        if not meter_seed_blocked(surface, item.xy, road_key=road_key)
    ]
    owned = _keep_owned_seeds(samples, rect)
    return owned, _refs_for_owned_seeds(refs, owned)


def sample_shore_meter(
    surface: MeterGradeSurface,
    *,
    road_key: str,
    world: World | None = None,
    rect: ColumnBounds | None = None,
    halo: int = 0,
) -> tuple[list[SampleCell], set[Coord]]:
    """SHORE hydro role = ref; landward ortho neighbor = seed."""
    if not surface.hydrology:
        return [], set()

    bounds = _sample_bounds(rect, halo)
    shore_refs: list[tuple[Coord, int]] = []
    cells = (
        _iter_z_in_bounds(surface, bounds)
        if bounds is not None
        else surface.surface_z.items()
    )
    for xy, z in cells:
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

    samples, refs = sample_landward_of_refs(shore_refs, neighbor_site=neighbor_site)
    owned = _keep_owned_seeds(samples, rect)
    return owned, _refs_for_owned_seeds(refs, owned)


def sample_road_shoulder_meter(
    surface: MeterGradeSurface,
    *,
    road_key: str,
    world: World | None = None,
    rect: ColumnBounds | None = None,
    halo: int = 0,
) -> tuple[list[SampleCell], set[Coord]]:
    """Road cell = ref; adjacent non-road land with Δz = seed (both sides)."""
    bounds = _sample_bounds(rect, halo)
    cells = (
        _iter_z_in_bounds(surface, bounds)
        if bounds is not None
        else surface.surface_z.items()
    )
    road_refs: list[tuple[Coord, int]] = []
    for xy, z in cells:
        if surface.terrain_at(xy) != road_key:
            continue
        road_refs.append((xy, int(z)))
    if not road_refs:
        return [], set()

    def neighbor_site(seed: Coord) -> tuple[str, int] | None:
        if seed not in surface.surface_z:
            return None
        if meter_seed_blocked(surface, seed, road_key=road_key):
            return None
        terrain_lo = surface.terrain_at(seed)
        z_lo = surface.z_at(seed)
        if not terrain_lo or z_lo is None:
            return None
        return str(terrain_lo), int(z_lo)

    samples, refs = sample_landward_of_refs(road_refs, neighbor_site=neighbor_site)
    samples = [item for item in samples if has_relief_dz(item.dz)]
    owned = _keep_owned_seeds(samples, rect)
    return owned, _refs_for_owned_seeds(refs, owned)


def sample_ravine_meter(
    surface: MeterGradeSurface,
    *,
    road_key: str,
    world: World | None = None,
    rect: ColumnBounds | None = None,
    halo: int = 0,
) -> tuple[list[SampleCell], set[Coord]]:
    """Bank (non-ravine) = ref; ortho ravine mask cell = seed.

    Membership is the depression mask, not open_land downhill (floor seed).
    Flat floor (no ortho bank / Δz=0) is not a site.
    """
    ravine_key = ravine_terrain_key(world)
    bounds = _sample_bounds(rect, halo)
    cells = (
        _iter_z_in_bounds(surface, bounds)
        if bounds is not None
        else surface.surface_z.items()
    )
    bank_refs: list[tuple[Coord, int]] = []
    for xy, z in cells:
        terrain = surface.terrain_at(xy)
        if terrain is None or terrain == ravine_key:
            continue
        sx, sy = xy
        if not any(
            surface.terrain_at((sx + dx, sy + dy)) == ravine_key
            for dx, dy in CARDINAL_ORTHO_DELTAS
        ):
            continue
        bank_refs.append((xy, int(z)))
    if not bank_refs:
        return [], set()
    bank_refs.sort(key=lambda item: item[0])

    def neighbor_site(seed: Coord) -> tuple[str, int] | None:
        if surface.terrain_at(seed) != ravine_key:
            return None
        if meter_seed_blocked(surface, seed, road_key=road_key):
            return None
        z_lo = surface.z_at(seed)
        if z_lo is None:
            return None
        return ravine_key, int(z_lo)

    samples, refs = sample_landward_of_refs(bank_refs, neighbor_site=neighbor_site)
    samples = [item for item in samples if has_relief_dz(item.dz)]
    owned = _keep_owned_seeds(samples, rect)
    return owned, _refs_for_owned_seeds(refs, owned)
