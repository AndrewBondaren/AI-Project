"""Pack L0 tile planner — light (bootstrap+cap) vs full (all location tiles).

docs/tz_world_pack_storage.md § Bake modes (WP-27).
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.passes.bootstrapMacroTiles import (
    bootstrap_macro_tiles,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.bake.packTileCollect import full_location_l0_tiles
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
            tiles = full_location_l0_tiles(world, locations)
            return PackTilePlan(
                scope="full",
                tiles=[PackTileRef(gx=gx, gy=gy) for gx, gy in tiles],
                capped=False,
                cap_applied=None,
            )

        cap = resolve_light_tile_cap(max_tiles, defaults=self._defaults)
        ordered = bootstrap_macro_tiles(
            world,
            locations,
            surface_ctx.coarse_hydro,
            surface_ctx.sparse_meter_hydro,
            max_tiles=max_tiles,
            defaults=self._defaults,
        )
        return PackTilePlan(
            scope="light",
            tiles=[PackTileRef(gx=gx, gy=gy) for gx, gy in ordered],
            capped=cap is not None,
            cap_applied=cap,
        )
