"""Outdoor settlement facade: gates and contract order. Not DAG.

C23/C24 bodies live in internal jobs. This module does not import planner
districts/streets or pack blob framing.
"""

from __future__ import annotations

import logging

from app.application.worldData.buildingTemplateLibraryService import BuildingTemplateLibraryService
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_settlement_c11_start,
    log_pack_settlement_skip_not_in_index,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationsIndexRead import (
    location_uid_in_pack_index,
    location_uids_in_pack_index,
)
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    MaterializeBatchResult,
    MaterializeResult,
    SettlementOutdoorConflictError,
    SettlementOutdoorError,
    SettlementOutdoorNotFoundError,
    SettlementOutdoorPackMissingError,
    TopologyBatchResult,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorLog import (
    finish_c11,
    finish_c11_error,
    skipped_c11,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorPackingJob import (
    SettlementOutdoorPackingJob,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    is_settlement_outdoor_target,
    packed_district_uids,
    packing_targets,
    resolve_packing_queue,
    should_skip_materialize,
    topology_targets,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import (
    SettlementOutdoorSqlPersist,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    DistrictAnchorError,
    has_authored_non_district_children,
    topology_census,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopologyJob import (
    SettlementOutdoorTopologyJob,
)
from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    WallClock,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.iWorldRepository import IWorldRepository

logger = logging.getLogger(__name__)


class SettlementOutdoorOrchestrator:

    def __init__(
        self,
        world_repo: IWorldRepository,
        location_repo: INamedLocationRepository,
        sql_persist: SettlementOutdoorSqlPersist,
        generator: SettlementGeneratorService,
        writer_for,
        facade_for,
        pack_context_for,
        library: BuildingTemplateLibraryService,
        node_repo: IConnectionNodeRepository,
        edge_repo: IConnectionEdgeRepository,
    ) -> None:
        self._worlds = world_repo
        self._locations = location_repo
        self._writer_for = writer_for
        self._facade_for = facade_for
        self._pack_context_for = pack_context_for
        self._generator = generator
        self._topology = SettlementOutdoorTopologyJob(
            location_repo, sql_persist, generator, node_repo,
        )
        self._packing = SettlementOutdoorPackingJob(
            generator, sql_persist, self._invalidate,
            library, node_repo, edge_repo,
        )

    def _require_pack(self, world: World) -> MapCellQueryFacade:
        facade: MapCellQueryFacade = self._facade_for(world.world_uid)
        if not facade.has_pack_for(world):
            raise SettlementOutdoorPackMissingError(
                f"World '{world.world_uid}' has no baked pack"
            )
        return facade

    async def plan_topology(self, world_uid: str) -> TopologyBatchResult:
        world = await self._require_world(world_uid)
        facade = self._require_pack(world)
        locs = await self._locations.list_by_world_insert_order(world_uid)
        return await self._topology.plan_batch(
            world, topology_targets(world, locs), facade,
        )

    async def materialize(
        self,
        world_uid: str,
        location_uid: str,
        *,
        skip_if_initialized: bool = True,
        district_uid: str | None = None,
        at_x: int | None = None,
        at_y: int | None = None,
    ) -> MaterializeResult:
        world = await self._require_world(world_uid)
        settlement = await self._require_settlement(world_uid, location_uid)
        facade = self._require_pack(world)
        writer: WorldPackWriter = self._writer_for(world)
        if not location_uid_in_pack_index(writer.paths, settlement.location_uid):
            log_pack_settlement_skip_not_in_index(
                world_uid, location_uid=location_uid,
            )
            return MaterializeResult(location_uid=location_uid, status="skipped")
        log_pack_settlement_c11_start(world_uid, location_uid=location_uid)
        clock = WallClock()
        try:
            children = await self._locations.get_children(location_uid)
            if has_authored_non_district_children(children):
                return skipped_c11(world_uid, location_uid, clock)
            has_anchor = bool(district_uid) or at_x is not None or at_y is not None
            if (
                skip_if_initialized
                and not has_anchor
                and await should_skip_materialize(
                    settlement, writer, self._locations, children=children,
                )
            ):
                return skipped_c11(world_uid, location_uid, clock)
            census = topology_census(children)
            if not census:
                raise SettlementOutdoorConflictError(
                    f"Location '{location_uid}' has no C23 topology census"
                )
            try:
                has_anchor, queue = resolve_packing_queue(
                    census, packed_district_uids(writer, location_uid),
                    district_uid=district_uid, at_x=at_x, at_y=at_y,
                )
            except DistrictAnchorError as exc:
                raise SettlementOutdoorError(str(exc)) from exc
            if has_anchor:
                if await should_skip_materialize(
                    settlement, writer, self._locations,
                    district_uid=queue[0].location_uid, children=children,
                ):
                    return skipped_c11(world_uid, location_uid, clock)
            elif not queue:
                return skipped_c11(world_uid, location_uid, clock)
            result, nbytes, pipeline = await self._packing.run_queue(
                world, settlement, facade, writer, children, queue, clock,
            )
            return finish_c11(
                world_uid, result, clock, pipeline=pipeline, encode_bytes=nbytes,
            )
        except Exception:
            finish_c11_error(world_uid, location_uid, clock)
            raise

    async def materialize_all(
        self, world_uid: str, *, skip_if_initialized: bool = True,
    ) -> MaterializeBatchResult:
        world = await self._world_with_pack(world_uid)
        locs = await self._locations.list_by_world_insert_order(world_uid)
        return await self._materialize_many(
            world_uid, packing_targets(locs, self._index_uids(world)),
            skip_if_initialized=skip_if_initialized,
        )

    async def materialize_under(
        self,
        world_uid: str,
        ancestor_uid: str,
        *,
        skip_if_initialized: bool = True,
    ) -> MaterializeBatchResult:
        world = await self._require_world(world_uid)
        ancestor = await self._locations.get_by_id(ancestor_uid)
        if ancestor is None or ancestor.world_uid != world_uid:
            raise SettlementOutdoorNotFoundError(
                f"Location '{ancestor_uid}' not found"
            )
        self._require_pack(world)
        descendants = await self._locations.list_descendants(ancestor_uid)
        return await self._materialize_many(
            world_uid, packing_targets(descendants, self._index_uids(world)),
            skip_if_initialized=skip_if_initialized,
        )

    async def materialize_state(
        self,
        world_uid: str,
        state_uid: str,
        *,
        skip_if_initialized: bool = True,
    ) -> MaterializeBatchResult:
        world = await self._world_with_pack(world_uid)
        locs = await self._locations.list_by_state_uids(world_uid, [state_uid])
        return await self._materialize_many(
            world_uid, packing_targets(locs, self._index_uids(world)),
            skip_if_initialized=skip_if_initialized,
        )

    async def _materialize_many(
        self,
        world_uid: str,
        targets: list[NamedLocation],
        *,
        skip_if_initialized: bool,
    ) -> MaterializeBatchResult:
        results: list[MaterializeResult] = []
        failed: list[str] = []
        for loc in sorted(targets, key=lambda item: item.location_uid):
            try:
                results.append(await self.materialize(
                    world_uid, loc.location_uid,
                    skip_if_initialized=skip_if_initialized,
                ))
            except Exception as exc:
                logger.exception(
                    "SettlementOutdoorOrchestrator | settlement=%s failed",
                    loc.location_uid,
                )
                failed.append(loc.location_uid)
                results.append(MaterializeResult(
                    location_uid=loc.location_uid,
                    status="error",
                    error=str(exc),
                ))
        return MaterializeBatchResult(results=results, failed_uids=failed)

    def _index_uids(self, world: World) -> frozenset[str]:
        return location_uids_in_pack_index(self._writer_for(world).paths)

    async def _world_with_pack(self, world_uid: str) -> World:
        world = await self._require_world(world_uid)
        self._require_pack(world)
        return world

    async def _require_world(self, world_uid: str) -> World:
        world = await self._worlds.get_by_id(world_uid)
        if world is None:
            raise SettlementOutdoorNotFoundError(f"World '{world_uid}' not found")
        return world

    async def _require_settlement(
        self, world_uid: str, location_uid: str,
    ) -> NamedLocation:
        loc = await self._locations.get_by_id(location_uid)
        if loc is None or loc.world_uid != world_uid:
            raise SettlementOutdoorNotFoundError(
                f"Location '{location_uid}' not found"
            )
        if not is_settlement_outdoor_target(loc):
            raise SettlementOutdoorError(
                f"Location '{location_uid}' is not a settlement outdoor target"
            )
        return loc

    def _invalidate(self, world: World, facade: MapCellQueryFacade) -> None:
        context: PackReadContext = self._pack_context_for(world.world_uid)
        context.invalidate_pack(world)
        facade.invalidate_city_structure()
