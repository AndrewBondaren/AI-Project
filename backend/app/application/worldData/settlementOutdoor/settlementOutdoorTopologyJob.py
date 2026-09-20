"""Internal C23 topology job — skip, terrain, generator, extract, persist.

Not a public orchestrator. Facade owns pack gates and settlement-like list.
"""

from __future__ import annotations

import logging

from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_settlement_topology_batch_done,
    log_pack_settlement_topology_batch_start,
    log_pack_settlement_topology_start,
)
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volume_for_location,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    SettlementOutdoorError,
    TopologyBatchResult,
    TopologyResult,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    extract_topology,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorLog import (
    finish_topology,
    finish_topology_error,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import (
    SettlementOutdoorSqlPersist,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    city_nodes_for_settlement,
    should_skip_topology,
    topology_districts,
)
from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    SettlementPipelineTimings,
    WallClock,
)
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository

logger = logging.getLogger(__name__)


class SettlementOutdoorTopologyJob:

    def __init__(
        self,
        location_repo: INamedLocationRepository,
        sql_persist: SettlementOutdoorSqlPersist,
        generator: SettlementGeneratorService,
        node_repo: IConnectionNodeRepository,
    ) -> None:
        self._locations = location_repo
        self._sql = sql_persist
        self._generator = generator
        self._nodes = node_repo

    async def plan_batch(
        self,
        world: World,
        settlements: list[NamedLocation],
        facade: MapCellQueryFacade,
    ) -> TopologyBatchResult:
        ordered = sorted(settlements, key=lambda loc: loc.location_uid)
        results: list[TopologyResult] = []
        failed: list[str] = []
        batch_t0 = log_pack_settlement_topology_batch_start(
            world.world_uid, settlements=len(ordered),
        )
        for loc in ordered:
            log_pack_settlement_topology_start(
                world.world_uid, location_uid=loc.location_uid,
            )
            clock = WallClock()
            try:
                result, pipeline = await self.plan_one(world, loc, facade)
                results.append(finish_topology(
                    world.world_uid, result, clock, pipeline=pipeline,
                ))
            except Exception as exc:
                logger.exception(
                    "SettlementOutdoorTopologyJob | settlement=%s failed",
                    loc.location_uid,
                )
                finish_topology_error(
                    world.world_uid, loc.location_uid, clock,
                )
                failed.append(loc.location_uid)
                results.append(TopologyResult(
                    location_uid=loc.location_uid,
                    status="error",
                    error=str(exc),
                ))
        log_pack_settlement_topology_batch_done(
            world.world_uid, settlements=len(ordered), started_at=batch_t0,
        )
        return TopologyBatchResult(results=results, failed_uids=failed)

    async def plan_one(
        self,
        world: World,
        settlement: NamedLocation,
        facade: MapCellQueryFacade,
        *,
        force: bool = False,
    ) -> tuple[TopologyResult, SettlementPipelineTimings]:
        clock = WallClock()
        children = await self._locations.get_children(settlement.location_uid)
        world_nodes = await self._nodes.get_by_world(world.world_uid)
        settlement_nodes = city_nodes_for_settlement(
            world_nodes, settlement.location_uid,
        )
        if not force and should_skip_topology(children, settlement_nodes):
            setup_s = clock.total()
            return (
                TopologyResult(
                    location_uid=settlement.location_uid,
                    status="skipped",
                    districts=len(topology_districts(children)),
                ),
                SettlementPipelineTimings(setup_s=setup_s, topology_s=setup_s),
            )

        volume = territory_volume_for_location(world, settlement)
        if volume is None:
            raise SettlementOutdoorError(
                f"Location '{settlement.location_uid}' has no territory volume"
            )
        setup_s = clock.lap()
        terrain_cells = await facade.get_footprint_terrain(
            world,
            x0=volume.x0,
            y0=volume.y0,
            x1=volume.x1,
            y1=volume.y1,
            location_uid=settlement.location_uid,
        )
        topo_terrain_s = clock.lap()
        slots, city_nodes, city_edges = self._generator.plan_slots_and_city_graph(
            world, settlement, terrain_cells or None,
        )
        topo_slots_s = clock.lap()
        extracted = extract_topology(settlement, slots, city_nodes, city_edges)
        topo_extract_s = clock.lap()
        await self._sql.persist_topology(extracted)
        topo_sql_s = clock.lap()
        gates = sum(
            1 for node in city_nodes
            if node.node_type == ConnectionNodeType.SETTLEMENT_GATE.value
            and node.graph_level == GraphLevel.CITY.value
        )
        pipeline = SettlementPipelineTimings(
            setup_s=setup_s,
            topo_terrain_s=topo_terrain_s,
            topo_slots_s=topo_slots_s,
            topo_extract_s=topo_extract_s,
            topo_sql_s=topo_sql_s,
            topology_s=clock.total(),
        )
        return (
            TopologyResult(
                location_uid=settlement.location_uid,
                status="planned",
                districts=len(extracted.districts),
                gates=gates,
            ),
            pipeline,
        )
