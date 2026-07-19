"""Resolve materialization / bake extent from world_bounds or anchor AABB."""

from __future__ import annotations

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.climate.locations import static_map_anchors
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.application.worldData.generators.terrain.worldMapSettings import grid_bbox_padding
from app.dataModel.worldPack.worldBounds import WorldBounds
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _declared_grid_bbox(world: World) -> GridBBox | None:
    bounds = WorldBounds.try_parse(world.world_bounds)
    if bounds is None:
        return None
    return GridBBox(
        x_min=bounds.x_min,
        x_max=bounds.x_max,
        y_min=bounds.y_min,
        y_max=bounds.y_max,
    )


def grid_bbox_from_locations(
    world: World,
    locations: list[NamedLocation],
) -> GridBBox | None:
    declared = _declared_grid_bbox(world)
    if declared is not None:
        return declared

    padding = grid_bbox_padding(world)
    anchors = static_map_anchors(locations)
    if not anchors:
        return None
    cell_m = cell_size_m(world)
    positions = [
        (meters_to_grid_x(l.map_x, cell_m), meters_to_grid_y(l.map_y, cell_m))
        for l in anchors
    ]
    return GridBBox(
        x_min=min(p[0] for p in positions) - padding,
        x_max=max(p[0] for p in positions) + padding,
        y_min=min(p[1] for p in positions) - padding,
        y_max=max(p[1] for p in positions) + padding,
    )
