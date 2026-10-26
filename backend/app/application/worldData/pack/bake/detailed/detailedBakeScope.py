"""detailed_bake scope resolution — request → refine tile plan.

What to refine lives here (tiles / rects / volumes / role); the loop is
``detailedBakeRefine``; ordering and logging — ``PackDetailedBakeOrchestrator``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volume_for_location,
    territory_volumes_by_location,
)
from app.application.worldData.pack.read.locationsIndexRead import (
    location_uid_in_pack_index,
)
from app.application.worldData.pack.refine.fine.chunk.fineChunkGeom import (
    expected_fine_chunks,
    rects_for_macro_tile,
    rects_overlapping_volume,
    tiles_covering_volume,
)
from app.dataModel.worldPack.bake.detailedBakeScope import (
    DetailedBakeRequest,
    refine_role_for_detailed_scope,
)
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.meta.worldPackManifest import ChunkRefineRole
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

RectsForTile = Callable[[int, int], list[ColumnRect]]


@dataclass(frozen=True, slots=True)
class DetailedScopePlan:
    """Resolved scope — everything the refine loop needs."""

    tiles: list[tuple[int, int]]
    rects_for_tile: RectsForTile
    location_volumes: list[TerritoryVolume]
    refine_role: ChunkRefineRole
    expected_chunks_for_status: Callable[[int, int], int] | None
    location_uid: str | None


def resolve_detailed_scope(
    world: World,
    locations: list[NamedLocation],
    writer: WorldPackWriter,
    request: DetailedBakeRequest,
) -> DetailedScopePlan | None:
    """``None`` = location absent from the pack index (skip, not an error)."""
    if request.scope == "location":
        return _location_plan(world, locations, writer, request)
    return _wilderness_plan(world, locations, writer, request)


def _location_plan(
    world: World,
    locations: list[NamedLocation],
    writer: WorldPackWriter,
    request: DetailedBakeRequest,
) -> DetailedScopePlan | None:
    location_uid = request.location_uid
    assert location_uid is not None
    location = next(
        (loc for loc in locations if loc.location_uid == location_uid), None,
    )
    if location is None:
        raise ValueError(f"location_uid not found: {location_uid}")
    if not location_uid_in_pack_index(writer.paths, location_uid):
        return None
    volume = territory_volume_for_location(world, location)
    if volume is None:
        raise ValueError(
            f"location {location_uid} has no territory volume (missing map_x/map_y)",
        )
    tiles = tiles_covering_volume(world, volume)
    if not tiles:
        raise ValueError(f"location {location_uid}: no macro-tiles for territory")
    return DetailedScopePlan(
        tiles=tiles,
        rects_for_tile=lambda gx, gy: rects_overlapping_volume(world, volume, gx, gy),
        location_volumes=[volume],
        refine_role=refine_role_for_detailed_scope("location"),
        expected_chunks_for_status=None,
        location_uid=location_uid,
    )


def _wilderness_plan(
    world: World,
    locations: list[NamedLocation],
    writer: WorldPackWriter,
    request: DetailedBakeRequest,
) -> DetailedScopePlan:
    return DetailedScopePlan(
        tiles=wilderness_tiles(
            writer,
            max_tiles=request.max_tiles,
            tile_gx=request.tile_gx,
            tile_gy=request.tile_gy,
        ),
        rects_for_tile=lambda gx, gy: rects_for_macro_tile(world, gx, gy),
        location_volumes=[
            vol for _, vol in territory_volumes_by_location(world, locations)
        ],
        refine_role=refine_role_for_detailed_scope("wilderness"),
        expected_chunks_for_status=lambda gx, gy: expected_fine_chunks(world, gx, gy),
        location_uid=None,
    )


def wilderness_tiles(
    writer: WorldPackWriter,
    *,
    max_tiles: int,
    tile_gx: int | None = None,
    tile_gy: int | None = None,
) -> list[tuple[int, int]]:
    """Explicit tile or all L0-baked tiles without completed refine."""
    if tile_gx is not None and tile_gy is not None:
        tile = writer.manifest.tile_entry(tile_gx, tile_gy)
        if tile is None or not tile.world_map_path:
            raise ValueError(
                f"wilderness tile=({tile_gx},{tile_gy}) has no L0 world_map_path "
                "(run full/light bake first)",
            )
        if tile.wilderness_refine_status == "complete":
            return []
        return [(tile_gx, tile_gy)]

    out: list[tuple[int, int]] = []
    for tile in writer.manifest.tiles:
        if not tile.world_map_path:
            continue
        if tile.wilderness_refine_status == "complete":
            continue
        out.append((tile.gx, tile.gy))
    out.sort(key=lambda t: (t[1], t[0]))
    if max_tiles > 0:
        return out[:max_tiles]
    return out
