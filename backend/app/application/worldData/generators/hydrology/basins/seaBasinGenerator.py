"""Declared coastal sea basin carve — D HY-2 scope COASTAL_SEA."""

from __future__ import annotations

import logging
from typing import Any

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.basins.lakeBasinGenerator import _merge_bbox
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import carve_deepening_bands
from app.application.worldData.generators.hydrology.load.resolveHydrologyBands import resolve_hydrology_bands
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.hydrology.types import HydrologyMasterInput
from app.application.worldData.generators.hydrology.waterBodyIdentity import (
    AutoWaterBodyRole,
    water_body_uid_for,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology

logger = logging.getLogger(__name__)


def generate_coastal_sea(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    if not master.declared_coastline_specs:
        return {}, None

    bands = resolve_hydrology_bands("seas", world, world_uid=master.world_uid)
    z_sea = resolve_z_sea(world)
    topology = resolve_hydrology_topology(world, heightmap)
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    dirty: GridBBox | None = None

    for spec in master.declared_coastline_specs:
        cells = rasterize_segments(spec.segments, topology=topology)
        if not cells:
            # A declare entirely in planar void still has identity and diagnostics.
            # The carver clips its output; these raw cells are only an identity key.
            cells = rasterize_segments(spec.segments)
        if not cells:
            continue
        uid = water_body_uid_for(spec.location_uid, AutoWaterBodyRole.SEA, min(cells))
        result = carve_deepening_bands(
            heightmap,
            spec.segments,
            bands,
            topology=topology,
            water_body_uid=uid,
            z_sea=z_sea,
        )
        if not any(cell.role == HydrologyCellRole.COASTAL_SEA for cell in result.by_cell.values()):
            # With no open water, band indices retain every original flood distance.
            # Land shore is index 0 and must not count as water.
            water_extent = max((cell.deepening_index or 0 for cell in result.by_cell.values()), default=0)
            if water_extent == 0 and any(a != b for a, b in spec.segments):
                logger.warning(
                    "declared coastline → water_dist=0 (water side outside bounds?) | world=%s water_body_uid=%s segments=%d",
                    master.world_uid, uid, len(spec.segments),
                )
            elif 0 < water_extent <= bands.min:
                logger.warning(
                    "declared coastline → water extent %d <= bands.min %d: no open water | world=%s water_body_uid=%s",
                    water_extent, bands.min, master.world_uid, uid,
                )
        merged.update(result.by_cell)
        dirty = _merge_bbox(result.by_cell, dirty)

    return merged, dirty
