"""Footprint reservation on world map grid — settlement ↔ map_cells."""

import logging

from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_grid_rect,
    settlement_origin,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def _surface_terrain(world: World) -> str:
    registry = world.terrain_registry or []
    types = {t["system_terrain"] for t in registry if "system_terrain" in t}
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
    location_uid = settlement; z = settlement.map_z.
    """
    _, _, gz = settlement_origin(settlement)
    gx0, gy0, gx1, gy1 = footprint_grid_rect(world, settlement, system_city_size)
    terrain = _surface_terrain(world)

    cells: list[MapCell] = []
    for gy in range(gy0, gy1):
        for gx in range(gx0, gx1):
            cells.append(MapCell(
                world_uid=world.world_uid,
                x=gx,
                y=gy,
                z=gz,
                system_terrain=terrain,
                location_uid=settlement.location_uid,
            ))

    logger.info(
        "plan_footprint_occupancy | settlement=%s grid=(%d,%d)-(%d,%d) z=%d cells=%d terrain=%s",
        settlement.location_uid,
        gx0,
        gy0,
        gx1,
        gy1,
        gz,
        len(cells),
        terrain,
    )
    return cells
