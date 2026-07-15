"""Pack L0 tile planner — light (bootstrap+cap) vs full (all location tiles).

docs/tz_world_pack_storage.md § Bake modes (WP-27).
"""

from __future__ import annotations

from app.application.worldData.generators.climate.locations import static_map_anchors
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import macro_tile_of
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.terrain.passes.bootstrapMacroTiles import (
    bootstrap_macro_tiles,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.dataModel.worldPack.packBakeDefaults import (
    PackBakeDefaults,
    resolve_light_tile_cap,
)
from app.dataModel.worldPack.packTilePlan import (
    PackTilePlan,
    PackTilePlanScope,
    PackTileRef,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

Tile = tuple[int, int]


def _full_location_tiles(
    world: World,
    locations: list[NamedLocation],
) -> list[Tile]:
    """All named_location macro-tiles ∪ declared hydro endpoints — no cap, no coarse flood."""
    cell_m = cell_size_m(world)
    tiles: set[Tile] = set()
    for loc in static_map_anchors(locations):
        tiles.add(macro_tile_of(loc.map_x, loc.map_y, cell_m))
    if is_hydrology_enabled(world):
        loaded = load_declared_hydrology(world, locations)
        for a, b in loaded.coastline_segments:
            tiles.add(macro_tile_of(a[0], a[1], cell_m))
            tiles.add(macro_tile_of(b[0], b[1], cell_m))
        for lake in loaded.lake_specs:
            for a, b in lake.shoreline_segments:
                tiles.add(macro_tile_of(a[0], a[1], cell_m))
                tiles.add(macro_tile_of(b[0], b[1], cell_m))
        for edge in loaded.river_edges:
            a, b = edge.segment
            tiles.add(macro_tile_of(a[0], a[1], cell_m))
            tiles.add(macro_tile_of(b[0], b[1], cell_m))
    return sorted(tiles, key=lambda t: (t[1], t[0]))


class PackTilePlanner:
    """Single SoT for expected L0 tile sets (light vs full)."""

    def __init__(self, *, bake_defaults: PackBakeDefaults | None = None) -> None:
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()

    def plan(
        self,
        world: World,
        locations: list[NamedLocation],
        surface_ctx: SurfaceTerrainContext,
        *,
        scope: PackTilePlanScope,
        max_tiles: int | None = None,
    ) -> PackTilePlan:
        if scope == "full":
            tiles = _full_location_tiles(world, locations)
            return PackTilePlan(
                scope="full",
                tiles=[PackTileRef(gx=gx, gy=gy) for gx, gy in tiles],
                capped=False,
                cap_applied=None,
            )

        cap = resolve_light_tile_cap(max_tiles, defaults=self._defaults)
        # bootstrap: None = no cap after resolve; pass 0 for uncapped
        bootstrap_cap = 0 if cap is None else cap
        ordered = bootstrap_macro_tiles(
            world,
            locations,
            surface_ctx.coarse_hydro,
            surface_ctx.sparse_meter_hydro,
            max_tiles=bootstrap_cap,
        )
        return PackTilePlan(
            scope="light",
            tiles=[PackTileRef(gx=gx, gy=gy) for gx, gy in ordered],
            capped=cap is not None,
            cap_applied=cap,
        )
