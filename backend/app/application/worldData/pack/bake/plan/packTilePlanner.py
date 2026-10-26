"""Pack L0 tile planner — light (location∪hydro tiles) vs full (world_bounds).

docs/tz_world_pack_storage.md § Bake modes (master contract 2026-07-19).
"""

from __future__ import annotations

from app.application.worldData.pack.bake.plan.packTileCollect import (
    light_l0_tiles,
    world_bounds_l0_tiles,
)
from app.dataModel.worldPack.bake.packBakeDefaults import (
    PackBakeDefaults,
    resolve_light_tile_cap,
)
from app.dataModel.worldPack.bake.packTilePlan import (
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
        *,
        scope: PackTilePlanScope,
        max_tiles: int | None = None,
    ) -> PackTilePlan:
        """Pure tile-set resolve — no surface planning inputs needed."""
        if scope == "full":
            tiles = world_bounds_l0_tiles(world, locations)
            return PackTilePlan(
                scope="full",
                tiles=[PackTileRef(gx=gx, gy=gy) for gx, gy in tiles],
                capped=False,
                cap_applied=None,
            )

        tiles = light_l0_tiles(world, locations)
        cap = resolve_light_tile_cap(max_tiles, defaults=self._defaults)
        if cap is not None:
            tiles = tiles[:cap]
        return PackTilePlan(
            scope="light",
            tiles=[PackTileRef(gx=gx, gy=gy) for gx, gy in tiles],
            capped=cap is not None,
            cap_applied=cap,
        )
