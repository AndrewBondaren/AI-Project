"""World map light bake — thin compose → writer (tz_map_light_bake / WP-15)."""

from __future__ import annotations

import time
from collections import Counter

from app.application.jsonValidation import terrain_system_keys
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
    prepare_surface_terrain_context,
)
from app.application.worldData.pack.bake.lightGrid.bake import compose_light_grid
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.locationsIndexBake import build_locations_index
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_surface_context,
    log_pack_world_map_bake_done,
    log_pack_world_map_bake_start,
    log_pack_world_map_tile_done,
)
from app.application.worldData.pack.bake.worldMapHydrology import world_map_hydro_role_from_cell
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_cells_per_tile
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _coarse_hydro_role_name(cell_hydro: object | None) -> str:
    return world_map_hydro_role_from_cell(cell_hydro).name


def _coarse_hydro_hist(coarse_hydro: dict[tuple[int, int], object]) -> dict[str, int]:
    return dict(Counter(_coarse_hydro_role_name(v) for v in coarse_hydro.values()))


def _surface_z_hist(surface_z: dict[tuple[int, int], int]) -> dict[str, int]:
    return {str(k): v for k, v in Counter(surface_z.values()).items()}


def _hydro_cell_role_label(cell_hydro: object | None) -> str | None:
    if cell_hydro is None:
        return None
    if isinstance(cell_hydro, MapCellHydrology):
        return cell_hydro.role.value if cell_hydro.role is not None else None
    if isinstance(cell_hydro, dict):
        raw = cell_hydro.get("role")
        return str(raw) if raw is not None else None
    raw = getattr(cell_hydro, "role", None)
    if raw is None:
        return None
    return str(getattr(raw, "value", raw))


class WorldMapBakeOrchestrator:
    """Persist L0 tiles from LightGridCompose — no per-field sampling here."""

    def bake_tiles(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        tiles: list[tuple[int, int]],
        *,
        surface_ctx: SurfaceTerrainContext | None = None,
        locations_index: LocationsIndexWire | None = None,
        **prepare_kwargs,
    ) -> int:
        world_uid = world.world_uid
        ctx_t0 = time.perf_counter()
        if surface_ctx is None:
            surface_ctx = prepare_surface_terrain_context(world, locations, **prepare_kwargs)
        if surface_ctx is None:
            log_pack_surface_context(world_uid, ok=False, started_at=ctx_t0)
            return 0
        log_pack_surface_context(
            world_uid,
            ok=True,
            started_at=ctx_t0,
            coarse_surface_z_n=len(surface_ctx.coarse_surface_z),
            coarse_hydro_n=len(surface_ctx.coarse_hydro),
            sparse_meter_hydro_n=len(surface_ctx.sparse_meter_hydro),
            meter_z_overrides_n=len(surface_ctx.meter_z_overrides),
            hydrology_enabled=is_hydrology_enabled(world),
            hydro_role_hist=_coarse_hydro_hist(surface_ctx.coarse_hydro),
            surface_z_hist=_surface_z_hist(surface_ctx.coarse_surface_z),
        )

        tile_m = cell_size_m(world)
        side = resolve_world_map_cells_per_tile(tile_m, world.world_map_cells_per_tile)
        scale = LightGridScale.from_tile(tile_m, side)
        index = locations_index or build_locations_index(locations)
        nodes = prepare_kwargs.get("nodes") or []
        edges = prepare_kwargs.get("edges") or []

        bake_ctx = LightGridBakeContext(
            world=world,
            locations=locations,
            locations_index=index,
            tiles=list(tiles),
            scale=scale,
            nodes=list(nodes),
            edges=list(edges),
            surface_planning=surface_ctx,
            pole_field=surface_ctx.pole_field,
            terrain_system_keys=terrain_system_keys(world),
        )
        compose = compose_light_grid(bake_ctx)

        writer.sync_world_metadata(world, cells_per_side=side)
        world_map_t0 = log_pack_world_map_bake_start(world_uid, tiles=len(tiles), cells_per_side=side)
        total = 0
        all_terrain: Counter[str] = Counter()
        all_hydro: Counter[str] = Counter()
        for idx, (gx, gy) in enumerate(tiles, start=1):
            tile_t0 = time.perf_counter()
            cells = compose.to_wire_tile(gx, gy)
            content_hash = writer.write_world_map_tile(gx, gy, cells, cells_per_side=side)
            total += len(cells)
            terrain_hist = dict(Counter(c.system_terrain or "?" for c in cells))
            hydro_hist = dict(Counter(c.hydrology_role.name for c in cells))
            surface_z_hist = dict(Counter(c.surface_z for c in cells))
            all_terrain.update(terrain_hist)
            all_hydro.update(hydro_hist)
            log_pack_world_map_tile_done(
                world_uid,
                gx,
                gy,
                tile_idx=idx,
                tiles_total=len(tiles),
                cells=len(cells),
                content_hash=content_hash,
                elapsed_ms=(time.perf_counter() - tile_t0) * 1000.0,
                terrain_hist=terrain_hist,
                hydro_hist=hydro_hist,
                surface_z_hist={str(k): v for k, v in surface_z_hist.items()},
                macro_hydro_role=_hydro_cell_role_label(surface_ctx.coarse_hydro.get((gx, gy))),
                macro_surface_z=int(surface_ctx.coarse_surface_z.get((gx, gy), 0)),
            )
        writer.manifest.bake_mode = "light"
        writer.recalc_manifest_counters()
        writer.save_manifest()
        log_pack_world_map_bake_done(
            world_uid,
            total_cells=total,
            tiles=len(tiles),
            started_at=world_map_t0,
            terrain_hist=dict(all_terrain),
            hydro_hist=dict(all_hydro),
        )
        return total

    def bake_tile(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        gx: int,
        gy: int,
        writer: WorldPackWriter,
        *,
        cells_per_side: int | None = None,
        locations: list[NamedLocation] | None = None,
        locations_index: LocationsIndexWire | None = None,
    ) -> tuple[list[WorldMapCellWire], str]:
        """Single-tile convenience wrapper around compose pipeline."""
        locs = locations or []
        tile_m = cell_size_m(world)
        side = cells_per_side or resolve_world_map_cells_per_tile(
            tile_m,
            world.world_map_cells_per_tile,
        )
        index = locations_index or build_locations_index(locs)
        bake_ctx = LightGridBakeContext(
            world=world,
            locations=locs,
            locations_index=index,
            tiles=[(gx, gy)],
            scale=LightGridScale.from_tile(tile_m, side),
            surface_planning=surface_ctx,
            pole_field=surface_ctx.pole_field,
            terrain_system_keys=terrain_system_keys(world),
        )
        compose = compose_light_grid(bake_ctx)
        cells = compose.to_wire_tile(gx, gy)
        content_hash = writer.write_world_map_tile(gx, gy, cells, cells_per_side=side)
        return cells, content_hash
