"""Declared coastal sea basin carve — D HY-2 scope COASTAL_SEA."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.basins.lakeBasinGenerator import _merge_bbox
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import carve_deepening_bands
from app.application.worldData.generators.hydrology.load.resolveHydrologyBands import resolve_hydrology_bands
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.hydrology.types import HydrologyMasterInput
from app.application.worldData.generators.hydrology.waterBodyIdentity import (
    AutoWaterBodyRole,
    water_body_uid_for,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def generate_coastal_sea(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    if not master.declared_coastline_specs:
        return {}, None

    bands = resolve_hydrology_bands("seas", world, world_uid=master.world_uid)
    z_sea = resolve_z_sea(world)
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    dirty: GridBBox | None = None

    for spec in master.declared_coastline_specs:
        cells = rasterize_segments(spec.segments)
        if not cells:
            continue
        uid = water_body_uid_for(spec.location_uid, AutoWaterBodyRole.SEA, min(cells))
        result = carve_deepening_bands(
            heightmap,
            spec.segments,
            bands,
            water_body_uid=uid,
            z_sea=z_sea,
        )
        merged.update(result.by_cell)
        dirty = _merge_bbox(result.by_cell, dirty)

    return merged, dirty
