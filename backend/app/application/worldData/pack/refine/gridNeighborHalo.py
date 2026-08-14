"""Read-only halo z from AABB-adjacent macro-tiles — not wrap / antagonist."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

from app.application.worldData.generators.coordinates.worldTile import (
    macro_tile_of,
    meter_bbox_for_tile,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.parentLightCache import ParentLightCache
from app.application.worldData.pack.read.parentLightLoad import load_parent_light
from app.application.worldData.pack.refine.columnBounds import (
    ColumnBounds,
    expand_rect,
    rect_contains,
)
from app.application.worldData.pack.refine.entryRingGeom import wilderness_chunk_origin
from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainColumnWire
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.worldBounds import WorldBounds

Coord = tuple[int, int]


def iter_halo_meters(this_bbox: ColumnBounds, halo: int) -> Iterator[Coord]:
    """Meters in the expanded strip, excluding ``this_bbox`` itself."""
    if halo <= 0:
        return
    expanded = expand_rect(this_bbox, halo)
    for y in range(expanded.y_min, expanded.y_max + 1):
        for x in range(expanded.x_min, expanded.x_max + 1):
            if rect_contains(this_bbox, x, y):
                continue
            yield x, y


def overlay_grid_neighbor_halos(
    state: TileSurfaceState,
    *,
    world_uid: str,
    tile_gx: int,
    tile_gy: int,
    this_bbox: ColumnBounds,
    halo: int,
    bounds: WorldBounds,
    reader: WorldPackReader,
    cache: ParentLightCache,
    tile_m: int,
    writer: WorldPackWriter | None = None,
    chunk_size: int | None = None,
) -> TileSurfaceState:
    """Merge neighbor L0 parent light, then already-baked fine columns if present."""
    if halo <= 0:
        return state
    out = state
    for facing in CARDINAL_FACINGS:
        neighbor = bounds.grid_neighbor(tile_gx, tile_gy, facing)
        if neighbor is None:
            continue
        ngx, ngy = neighbor
        parent = load_parent_light(
            world_uid, ngx, ngy, reader=reader, cache=cache, tile_m=tile_m,
        )
        if parent is not None:
            out = overlay_halo_from_parent(
                out, parent, this_bbox=this_bbox, halo=halo,
            )
        if writer is not None and chunk_size is not None:
            out = overlay_halo_from_wilderness(
                out,
                neighbor_gx=ngx,
                neighbor_gy=ngy,
                this_bbox=this_bbox,
                halo=halo,
                tile_m=tile_m,
                chunk_size=chunk_size,
                reader=reader,
                writer=writer,
            )
    return out


def overlay_halo_from_parent(
    state: TileSurfaceState,
    parent: ParentLightTile,
    *,
    this_bbox: ColumnBounds,
    halo: int,
) -> TileSurfaceState:
    """Nearest L0 cell of ``parent`` for meters in the expanded halo (not this tile)."""
    if halo <= 0:
        return state
    new_z = dict(state.heightmap.surface_z)
    new_terrain = dict(state.surface_terrain or {})
    new_facing = dict(state.surface_facing or {})
    wrote = False
    for x, y in iter_halo_meters(this_bbox, halo):
        if macro_tile_of(x, y, parent.tile_m) != (parent.gx, parent.gy):
            continue
        tx, ty = parent.meters_to_tx_ty(x, y)
        cell = parent.cell_at(tx, ty)
        if cell is None:
            continue
        new_z[(x, y)] = int(cell.surface_z)
        if cell.system_terrain:
            new_terrain[(x, y)] = cell.system_terrain
        if cell.system_facing is not None:
            new_facing[(x, y)] = cell.system_facing
        wrote = True
    if not wrote:
        return state
    return _with_halo_maps(state, new_z, new_terrain, new_facing)


def overlay_halo_from_surface(
    state: TileSurfaceState,
    neighbor: TileSurfaceState,
    *,
    this_bbox: ColumnBounds,
    halo: int,
) -> TileSurfaceState:
    """Copy neighbor meter z/terrain/facing into this tile's halo strip."""
    if halo <= 0:
        return state
    src_z = neighbor.heightmap.surface_z
    src_terrain = neighbor.surface_terrain or {}
    src_facing = neighbor.surface_facing or {}
    new_z = dict(state.heightmap.surface_z)
    new_terrain = dict(state.surface_terrain or {})
    new_facing = dict(state.surface_facing or {})
    wrote = False
    for x, y in iter_halo_meters(this_bbox, halo):
        z = src_z.get((x, y))
        if z is None:
            continue
        new_z[(x, y)] = int(z)
        terrain = src_terrain.get((x, y))
        if terrain:
            new_terrain[(x, y)] = terrain
        facing = src_facing.get((x, y))
        if facing is not None:
            new_facing[(x, y)] = facing
        wrote = True
    if not wrote:
        return state
    return _with_halo_maps(state, new_z, new_terrain, new_facing)


def overlay_halo_from_wilderness(
    state: TileSurfaceState,
    *,
    neighbor_gx: int,
    neighbor_gy: int,
    this_bbox: ColumnBounds,
    halo: int,
    tile_m: int,
    chunk_size: int,
    reader: WorldPackReader,
    writer: WorldPackWriter,
) -> TileSurfaceState:
    """Overwrite halo meters with already-baked neighbor fine columns when present."""
    tile = writer.manifest.tile_entry(neighbor_gx, neighbor_gy)
    chunks = getattr(tile, "chunks", None) if tile is not None else None
    if not isinstance(chunks, (list, tuple)) or not chunks:
        return state
    halo_set = set(iter_halo_meters(this_bbox, halo))
    if not halo_set:
        return state
    meter_bbox = meter_bbox_for_tile(neighbor_gx, neighbor_gy, tile_m)
    new_z = dict(state.heightmap.surface_z)
    new_terrain = dict(state.surface_terrain or {})
    new_facing = dict(state.surface_facing or {})
    wrote = False
    for ref in chunks:
        cx = getattr(ref, "cx", None)
        cy = getattr(ref, "cy", None)
        if cx is None or cy is None:
            continue
        try:
            chunk = reader.read_wilderness_chunk(
                neighbor_gx, neighbor_gy, int(cx), int(cy),
            )
        except (OSError, ValueError, FileNotFoundError):
            continue
        origin_x, origin_y = wilderness_chunk_origin(
            meter_bbox, int(cx), int(cy), chunk_size,
        )
        for col in chunk.columns:
            xy = (origin_x + int(col.lx), origin_y + int(col.ly))
            if xy not in halo_set:
                continue
            z, terrain = _column_surface(col)
            if z is None:
                continue
            new_z[xy] = z
            if terrain:
                new_terrain[xy] = terrain
            if col.system_facing is not None:
                new_facing[xy] = col.system_facing
            wrote = True
    if not wrote:
        return state
    return _with_halo_maps(state, new_z, new_terrain, new_facing)


def _column_surface(col: FineTerrainColumnWire) -> tuple[int | None, str | None]:
    if not col.runs:
        return None, None
    top = max(col.runs, key=lambda run: max(run.z0, run.z1))
    return max(top.z0, top.z1), top.system_terrain


def _with_halo_maps(
    state: TileSurfaceState,
    surface_z: dict[Coord, int],
    surface_terrain: dict[Coord, str],
    surface_facing: dict[Coord, Facing],
) -> TileSurfaceState:
    heightmap = SurfaceHeightmap(
        world_uid=state.heightmap.world_uid,
        bbox=state.heightmap.bbox,
        surface_z=surface_z,
    )
    return replace(
        state,
        heightmap=heightmap,
        surface_terrain=surface_terrain or None,
        surface_facing=surface_facing or None,
    )
