"""Parcel geometry + AreaPlacement from C22 reservations."""

from __future__ import annotations

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    AreaPlacement,
    Reservation,
    YARD_PADDING_M,
)
from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import (
    BuildingLayoutCache,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    lookup_building_template,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
)
from app.dataModel.spatial.facing import Facing
from app.db.models.world import World

__all__ = [
    "AreaPlacement",
    "YARD_PADDING_M",
    "make_area_slot",
    "parcel_cells",
    "placements_from_reservations",
]


def _footprint_rect(fp: OccupiedFootprint, building_x: int, building_y: int) -> tuple[int, int, int, int]:
    x0 = building_x + fp.min_x
    y0 = building_y + fp.min_y
    x1 = x0 + fp.width - 1
    y1 = y0 + fp.depth - 1
    return x0, y0, x1, y1


def _parcel_rect(fp: OccupiedFootprint, building_x: int, building_y: int, pad: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = _footprint_rect(fp, building_x, building_y)
    p = max(0, pad)
    return x0 - p, y0 - p, x1 + p, y1 + p


def parcel_cells(
    fp: OccupiedFootprint,
    bx: int,
    by: int,
    yard_padding: int,
) -> list[tuple[int, int]]:
    """Footprint + courtyard padding. Same rect as packing collision."""
    x0, y0, x1, y1 = _parcel_rect(fp, bx, by, yard_padding)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def make_area_slot(
    fp: OccupiedFootprint,
    bx: int,
    by: int,
    facing: Facing,
    *,
    fallback_z: int = 0,
) -> AreaSlot:
    cells = parcel_cells(fp, bx, by, YARD_PADDING_M)
    return AreaSlot(cells=cells, ground_z=fallback_z, facing=facing)


def origin_in_reservation(
    fp: OccupiedFootprint,
    rect: tuple[int, int, int, int],
) -> tuple[int, int]:
    x0, y0, _x1, _y1 = rect
    return x0 + YARD_PADDING_M - fp.min_x, y0 + YARD_PADDING_M - fp.min_y


def footprint_fits_rect(fp: OccupiedFootprint, rect: tuple[int, int, int, int], bx: int, by: int) -> bool:
    px0, py0, px1, py1 = _parcel_rect(fp, bx, by, YARD_PADDING_M)
    rx0, ry0, rx1, ry1 = rect
    return px0 >= rx0 and py0 >= ry0 and px1 < rx1 and py1 < ry1


def placements_from_reservations(
    reservations: list[Reservation],
    cache: BuildingLayoutCache,
    world: World,
    skeleton: CitySkeleton,
    fallback_z: int,
) -> list[AreaPlacement]:
    _ = skeleton
    placements: list[AreaPlacement] = []
    for reservation in reservations:
        name = reservation.token.system_name
        template = lookup_building_template(world, name)
        fp = cache.envelope(name)
        if template is None or fp is None:
            continue
        bx, by = origin_in_reservation(fp, reservation.rect_xy)
        area_slot = make_area_slot(fp, bx, by, Facing.SOUTH, fallback_z=fallback_z)
        placements.append(AreaPlacement(
            area_slot=area_slot,
            template=template,
            building_x=bx,
            building_y=by,
            facing=Facing.SOUTH,
            reservation=reservation,
        ))
    return placements
