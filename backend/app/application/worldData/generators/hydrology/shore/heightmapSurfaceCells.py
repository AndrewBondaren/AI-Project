"""Heightmap → top-surface MapCell list for terrain feature detect — D HY-5b."""

from __future__ import annotations

from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.db.models.mapCell import MapCell


def heightmap_top_surface_cells(heightmap: SurfaceHeightmap) -> list[MapCell]:
    return [
        MapCell(
            world_uid=heightmap.world_uid,
            x=gx,
            y=gy,
            z=z,
            system_terrain="plains",
        )
        for (gx, gy), z in heightmap.surface_z.items()
    ]
