"""Flatten SettlementLayout → map_cells for persist."""

from dataclasses import replace

from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    cell_in_footprint_meters,
    footprint_meter_rect,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

_SETTLEMENT_TYPES = frozenset({"city", "town", "village", "camp", "hamlet"})


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
    Urban-only terrain от eager/lazy terrain не считается geometry.
    """
    if settlement.system_location_type not in _SETTLEMENT_TYPES:
        return False
    ox, oy, x1, y1, _ = footprint_meter_rect(world, settlement)
    for cell in existing_cells:
        if (
            cell.system_building_element
            and cell_in_footprint_meters(cell.x, cell.y, ox, oy, x1, y1)
        ):
            return False
    return True


def collect_map_cells_from_layout(
    world:      World,
    settlement: NamedLocation,
    layout:     SettlementLayout,
) -> list[MapCell]:
    """occupancy + building interior cells + barriers."""
    cells: list[MapCell] = list(layout.occupancy_cells)

    for district in layout.district_layouts:
        for area in district.area_layouts:
            bound = rebind_layout_to_building(
                area.building_layout,
                area.building_location,
            )
            cells.extend(bound.cells)
        cells.extend(district.barrier_cells)

    cells.extend(layout.barrier_cells)
    return cells
