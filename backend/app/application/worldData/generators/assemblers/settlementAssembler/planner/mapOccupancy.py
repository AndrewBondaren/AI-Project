"""Footprint reservation on world map grid — settlement ↔ map_cells."""

import logging

from app.application.worldData.generators.masterData import terrain_rows
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    settlement_grid_rect,
)
from app.application.worldData.generators.coordinates import (
    CoordinateSpace,
    settlement_origin_m,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def _surface_terrain(world: World) -> str:
    types = {t["system_terrain"] for t in terrain_rows(world) if "system_terrain" in t}
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
    for gy in range(rect.gy0, rect.gy1):
        for gx in range(rect.gx0, rect.gx1):
            cells.append(MapCell(
                world_uid=world.world_uid,
                x=gx,
                y=gy,
                z=origin.z,
                system_terrain=terrain,
                location_uid=settlement.location_uid,
            ))

    logger.info(
        "plan_footprint_occupancy | settlement=%s space=%s grid=(%d,%d)-(%d,%d)"
        " z=%d cells=%d terrain=%s",
        settlement.location_uid,
        CoordinateSpace.WORLD_SURFACE_GRID,
        rect.gx0,
        rect.gy0,
        rect.gx1,
        rect.gy1,
        origin.z,
        len(cells),
        terrain,
    )
    return cells
