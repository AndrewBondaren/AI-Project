"""Footprint reservation on world map grid — settlement ↔ map_cells."""

import logging

from app.application.jsonValidation import terrain_system_keys
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    settlement_grid_rect,
)
from app.application.worldData.generators.coordinates import cell_size_m, world_meter_xy
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def _surface_terrain(world: World) -> str:
    types = terrain_system_keys(world)
    if "urban" in types:
        return "urban"
    return "plains"


def plan_footprint_occupancy_cells(
    world:            World,
    settlement:       NamedLocation,
    system_city_size: str | None = None,
) -> list[MapCell]:
    """
    Маркирует global map cells под footprint поселения.
    CoordinateSpace: WORLD_SURFACE_GRID (MapCell.x/y = grid index).
    """
    origin = settlement_origin_m(settlement)
    rect = settlement_grid_rect(world, settlement, system_city_size)
    terrain = _surface_terrain(world)

    cells: list[MapCell] = []
    cell_m = cell_size_m(world)
    for gy in range(rect.gy0, rect.gy1):
        for gx in range(rect.gx0, rect.gx1):
            for ly in range(cell_m):
                for lx in range(cell_m):
                    xm, ym = world_meter_xy(gx, gy, lx, ly, cell_m)
                    cells.append(MapCell(
                        world_uid=world.world_uid,
                        x=xm,
                        y=ym,
                        z=origin.z,
                        system_terrain=terrain,
                        location_uid=settlement.location_uid,
                    ))

    logger.info(
        "plan_footprint_occupancy | settlement=%s space=fine_meters grid=(%d,%d)-(%d,%d)"
        " z=%d cells=%d terrain=%s cell_m=%d",
        settlement.location_uid,
        rect.gx0,
        rect.gy0,
        rect.gx1,
        rect.gy1,
        origin.z,
        len(cells),
        terrain,
        cell_m,
    )
    return cells
