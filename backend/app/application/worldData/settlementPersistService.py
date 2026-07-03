import logging
from dataclasses import dataclass, field

from app.api.schemas.imports import ImportResult
from app.application.worldData.connectionPersistService import (
    ConnectionPersistResult,
    ConnectionPersistService,
)
from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import (
    collect_geometry_meter_cells,
    collect_surface_grid_cells,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayoutExtract import (
    collect_building_locations,
    collect_connection_graph,
    collect_edge_cells,
    needs_settlement_outdoor_persist,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.settlementPersistScope import (
    OUTDOOR_SCOPES,
    SettlementPersistScope,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository

logger = logging.getLogger(__name__)


@dataclass
class SettlementPersistResult:
    scopes_applied: list[str]           = field(default_factory=list)
    scopes_skipped: list[str]           = field(default_factory=list)
    map_cells:      ImportResult        = field(default_factory=lambda: ImportResult(0, 0, 0))
    connections:    ConnectionPersistResult | None = None
    buildings:      ImportResult        = field(default_factory=lambda: ImportResult(0, 0, 0))

    def to_dict(self) -> dict:
        return {
            "scopes_applied": self.scopes_applied,
            "scopes_skipped": self.scopes_skipped,
            "map_cells":      self.map_cells.to_dict(),
            "connections":    self.connections.to_dict() if self.connections else None,
            "buildings":      self.buildings.to_dict(),
        }


class SettlementPersistService:

    def __init__(
        self,
        map_cell_service:       MapCellService,
        location_repo:          INamedLocationRepository,
        connection_persist:     ConnectionPersistService,
        connection_edge_repo:   IConnectionEdgeRepository,
    ) -> None:
        self._map_cells         = map_cell_service
        self._locations         = location_repo
        self._connection_persist = connection_persist
        self._connection_edges  = connection_edge_repo

    async def persist(
        self,
        world:      World,
        settlement: NamedLocation,
        *,
        layout:              SettlementLayout | None = None,
        occupancy_cells:     list[MapCell] | None = None,
        scopes:              frozenset[SettlementPersistScope],
        skip_if_initialized: bool = True,
    ) -> SettlementPersistResult:
        result = SettlementPersistResult()

        if skip_if_initialized and scopes & OUTDOOR_SCOPES and layout is not None:
            existing_cells = await self._map_cells.get_all(world.world_uid)
            children       = await self._locations.get_children(settlement.location_uid)
            city_edges     = [
                e for e in await self._connection_edges.get_by_world(world.world_uid)
                if e.graph_level == "city"
            ]
            if not needs_settlement_outdoor_persist(
                settlement, world, existing_cells, children, city_edges,
            ):
                result.scopes_skipped = sorted(scopes, key=str)
                logger.info(
                    "SettlementPersistService | settlement=%s skipped — outdoor already init",
                    settlement.location_uid,
                )
                return result

        map_total = map_succeeded = 0
        conn_result: ConnectionPersistResult | None = None
        bld_total = bld_succeeded = 0

        for scope in sorted(scopes, key=str):
            if scope == SettlementPersistScope.OCCUPANCY:
                cells = occupancy_cells or []
                if not cells:
                    result.scopes_skipped.append(scope.value)
                    continue
                r = await self._map_cells.save_generated(cells)
                map_total += r.total
                map_succeeded += r.succeeded
                result.scopes_applied.append(scope.value)

            elif scope == SettlementPersistScope.MAP_CELLS_SURFACE:
                if layout is None:
                    result.scopes_skipped.append(scope.value)
                    continue
                cells = collect_surface_grid_cells(layout)
                r = await self._map_cells.save_generated(cells)
                map_total += r.total
                map_succeeded += r.succeeded
                result.scopes_applied.append(scope.value)

            elif scope == SettlementPersistScope.MAP_CELLS_GEOMETRY:
                if layout is None:
                    result.scopes_skipped.append(scope.value)
                    continue
                cells = collect_geometry_meter_cells(layout)
                r = await self._map_cells.save_generated(cells)
                map_total += r.total
                map_succeeded += r.succeeded
                result.scopes_applied.append(scope.value)

            elif scope == SettlementPersistScope.CONNECTIONS_CITY:
                if layout is None:
                    result.scopes_skipped.append(scope.value)
                    continue
                nodes, edges = collect_connection_graph(layout, frozenset({GraphLevel.CITY}))
                cells = collect_edge_cells(layout)
                conn_result = await self._connection_persist.persist_graph(nodes, edges, cells)
                result.scopes_applied.append(scope.value)

            elif scope == SettlementPersistScope.CONNECTIONS_DISTRICT:
                if layout is None:
                    result.scopes_skipped.append(scope.value)
                    continue
                nodes, edges = collect_connection_graph(layout, frozenset({GraphLevel.DISTRICT}))
                part = await self._connection_persist.persist_graph(nodes, edges, [])
                if conn_result is None:
                    conn_result = part
                else:
                    conn_result = ConnectionPersistResult(
                        nodes=ImportResult(
                            total=conn_result.nodes.total + part.nodes.total,
                            succeeded=conn_result.nodes.succeeded + part.nodes.succeeded,
                            failed=0,
                        ),
                        edges=ImportResult(
                            total=conn_result.edges.total + part.edges.total,
                            succeeded=conn_result.edges.succeeded + part.edges.succeeded,
                            failed=0,
                        ),
                        edge_cells=conn_result.edge_cells,
                    )
                result.scopes_applied.append(scope.value)

            elif scope == SettlementPersistScope.BUILDINGS:
                if layout is None:
                    result.scopes_skipped.append(scope.value)
                    continue
                buildings = collect_building_locations(layout, settlement)
                for building in buildings:
                    bld_total += 1
                    existing = await self._locations.get_by_id(building.location_uid)
                    if existing is not None:
                        continue
                    await self._locations.upsert(building)
                    bld_succeeded += 1
                result.scopes_applied.append(scope.value)

        result.map_cells   = ImportResult(total=map_total, succeeded=map_succeeded, failed=0)
        result.connections = conn_result
        result.buildings   = ImportResult(total=bld_total, succeeded=bld_succeeded, failed=0)

        logger.info(
            "SettlementPersistService | settlement=%s applied=%s map_cells=%d buildings=%d/%d",
            settlement.location_uid,
            result.scopes_applied,
            map_succeeded,
            bld_succeeded,
            bld_total,
        )
        return result

    async def persist_outdoor(
        self,
        world:      World,
        settlement: NamedLocation,
        layout:     SettlementLayout,
        *,
        skip_if_initialized: bool = True,
    ) -> SettlementPersistResult:
        return await self.persist(
            world,
            settlement,
            layout=layout,
            scopes=OUTDOOR_SCOPES,
            skip_if_initialized=skip_if_initialized,
        )
