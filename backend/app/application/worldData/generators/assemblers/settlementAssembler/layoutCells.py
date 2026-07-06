"""Flatten SettlementLayout → map_cells for persist."""

import logging
from dataclasses import replace

from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    settlement_meter_rect,
)
from app.application.worldData.generators.coordinates import cell_in_local_meter_rect
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)

_SETTLEMENT_TYPES = frozenset({"city", "town", "village", "camp", "hamlet"})


def _is_settlement_location(settlement: NamedLocation) -> bool:
    if settlement.system_location_type == "settlement":
        return True
    kind = settlement.system_location_subtype or settlement.system_city_size
    return kind in _SETTLEMENT_TYPES


def rebind_layout_to_building(
    layout:   StructureLayout,
    building: NamedLocation,
) -> StructureLayout:
    """Probe/cache cells несут probe uid — перед persist привязать к реальному зданию."""
    cells = [
        replace(c, location_uid=building.location_uid)
        for c in layout.cells
    ]
    return StructureLayout(
        cells=cells,
        levels=layout.levels,
        passages=layout.passages,
        rooms=layout.rooms,
        occupied_footprint=layout.occupied_footprint,
    )


def needs_settlement_geometry(
    settlement:     NamedLocation,
    world:          World,
    existing_cells: list[MapCell],
) -> bool:
    """
    True если в footprint ещё нет сгенерированной застройки (building elements).
    Urban-only terrain / occupancy grid cells не считаются geometry.

    Проверяет только WORLD_LOCAL_METERS: system_building_element в meter rect footprint.
    """
    if not _is_settlement_location(settlement):
        return False
    rect = settlement_meter_rect(world, settlement)
    for cell in existing_cells:
        if not cell.system_building_element:
            continue
        if cell_in_local_meter_rect(cell.x, cell.y, rect):
            return False
    return True


def collect_surface_grid_cells(layout: SettlementLayout) -> list[MapCell]:
    """WORLD_SURFACE_GRID: footprint occupancy (grid index in MapCell.x/y)."""
    return list(layout.occupancy_cells)


def collect_geometry_meter_cells(layout: SettlementLayout) -> list[MapCell]:
    """WORLD_LOCAL_METERS: building interior/outdoor cells + settlement/district/area barriers."""
    cells: list[MapCell] = []

    for district in layout.district_layouts:
        for area in district.area_layouts:
            bound = rebind_layout_to_building(
                area.building_layout,
                area.building_location,
            )
            cells.extend(bound.cells)
            cells.extend(area.barrier_cells)
        cells.extend(district.barrier_cells)

    cells.extend(layout.barrier_cells)
    return cells


def collect_map_cells_from_layout(
    world:      World,
    settlement: NamedLocation,
    layout:     SettlementLayout,
) -> list[MapCell]:
    """
    Persist batch: surface grid occupancy + meter geometry.
    Option A — spaces stay separate until DB carries coordinate_space (v2).
    """
    grid_cells = collect_surface_grid_cells(layout)
    meter_cells = collect_geometry_meter_cells(layout)
    cells = grid_cells + meter_cells
    logger.info(
        "collect_map_cells_from_layout | settlement=%s total=%d "
        "surface_grid=%d meter_geometry=%d",
        settlement.location_uid,
        len(cells),
        len(grid_cells),
        len(meter_cells),
    )
    return cells
