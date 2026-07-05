"""Declared coastal sea basin carve — D HY-2 scope COASTAL_SEA."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.hydrology.deepeningBandCarver import carve_deepening_bands
from app.application.worldData.generators.terrain.hydrology.resolveHydrologyBands import resolve_hydrology_bands
from app.application.worldData.generators.terrain.hydrology.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.terrain.hydrology.types import HydrologyMasterInput
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def generate_coastal_sea(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    if not master.declared_coastline_segments:
        return {}, None

    bands = resolve_hydrology_bands("seas", world, world_uid=master.world_uid)
    z_sea = resolve_z_sea(world)
    result = carve_deepening_bands(
        heightmap,
        master.declared_coastline_segments,
        bands,
        z_sea=z_sea,
    )
    return result.by_cell, result.dirty_bbox
