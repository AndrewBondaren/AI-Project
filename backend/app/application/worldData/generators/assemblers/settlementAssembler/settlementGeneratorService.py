"""
Settlement generation service — lazy phase 2 (tz_city_generation.md §5).

Skeleton на NamedLocation — фаза 1 (world create).
Полная геометрия — SettlementAssembler + map_cells persist при первом входе.
"""

import logging

from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import (
    collect_geometry_meter_cells,
    collect_map_cells_from_layout,
    collect_surface_grid_cells,
    needs_settlement_geometry,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.mapOccupancy import (
    plan_footprint_occupancy_cells,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementAssembler import (
    SettlementAssembler,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


class SettlementGeneratorService:
    """
    Pure sync generation + helpers for lazy persist.
    Async persist — через MapCellService / map_cell_repo в engine node.
    """

    def __init__(self) -> None:
        self._assembler = SettlementAssembler()

    def plan_occupancy_only(
        self,
        world:      World,
        settlement: NamedLocation,
    ) -> list[MapCell]:
        """Только резерв footprint (можно вызвать при world create)."""
        return plan_footprint_occupancy_cells(world, settlement)

    def generate_layout(
        self,
        world:         World,
        settlement:    NamedLocation,
        terrain_cells: list[MapCell] | None = None,
    ) -> SettlementLayout:
        return self._assembler.assemble(world, settlement, terrain_cells)

    def collect_map_cells(
        self,
        world:      World,
        settlement: NamedLocation,
        layout:     SettlementLayout,
    ) -> list[MapCell]:
        return collect_map_cells_from_layout(world, settlement, layout)

    def collect_surface_grid_cells(self, layout: SettlementLayout) -> list[MapCell]:
        """WORLD_SURFACE_GRID occupancy — grid index in x/y."""
        return collect_surface_grid_cells(layout)

    def collect_geometry_meter_cells(self, layout: SettlementLayout) -> list[MapCell]:
        """WORLD_LOCAL_METERS — buildings + barriers."""
        return collect_geometry_meter_cells(layout)

    def generate_map_cells(
        self,
        world:         World,
        settlement:    NamedLocation,
        terrain_cells: list[MapCell] | None = None,
    ) -> tuple[SettlementLayout, list[MapCell]]:
        layout = self.generate_layout(world, settlement, terrain_cells)
        grid_cells   = self.collect_surface_grid_cells(layout)
        meter_cells  = self.collect_geometry_meter_cells(layout)
        cells        = grid_cells + meter_cells
        logger.info(
            "SettlementGeneratorService | settlement=%s map_cells=%d "
            "surface_grid=%d meter_geometry=%d",
            settlement.location_uid,
            len(cells),
            len(grid_cells),
            len(meter_cells),
        )
        return layout, cells

    @staticmethod
    def needs_geometry(
        settlement:     NamedLocation,
        world:          World,
        existing_cells: list[MapCell],
    ) -> bool:
        return needs_settlement_geometry(settlement, world, existing_cells)
