"""Apply pack climate fields onto merged cell view — CL-PACK-5."""

from __future__ import annotations

from app.application.worldData.generators.coordinates import (
    map_cell_fine_span,
    fine_to_grid_x,
    fine_to_grid_y,
)
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.dataModel.worldPack.mergeMapCells import MergedCellView
from app.db.models.world import World


def apply_climate_to_view(
    ctx: PackReadContext,
    world: World,
    view: MergedCellView,
) -> MergedCellView:
    if view.temperature_base is not None and view.rainfall is not None:
        return view
    cell_m = map_cell_fine_span(world)
    gx = int(fine_to_grid_x(view.x, cell_m))
    gy = int(fine_to_grid_y(view.y, cell_m))
    samples = []
    field_fine = ctx.climate_tile_field(world, gx, gy)
    if field_fine is not None:
        sample_fine = field_fine.sample_meters(view.x, view.y)
        if sample_fine is not None:
            samples.append(sample_fine)
    field_coarse = ctx.climate_field(world)
    if field_coarse is not None:
        sample_coarse = field_coarse.sample_macro(gx, gy)
        if sample_coarse is not None:
            samples.append(sample_coarse)
    if not samples:
        return view
    updates: dict = {}
    if view.temperature_base is None:
        for sample in samples:
            if sample.temperature_base is not None:
                updates["temperature_base"] = sample.temperature_base
                break
    if view.rainfall is None:
        for sample in samples:
            if sample.rainfall is not None:
                updates["rainfall"] = sample.rainfall
                break
    if not updates:
        return view
    return view.model_copy(update=updates)
