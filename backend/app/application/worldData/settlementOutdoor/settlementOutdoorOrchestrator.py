"""Outdoor settlement facade: gates and contract order. Not DAG.

C23/C24 bodies live in internal jobs. This module does not import planner
districts/streets or pack blob framing.
"""

from __future__ import annotations

import logging

from app.application.worldData.buildingTemplateLibraryService import BuildingTemplateLibraryService
from app.application.worldData.generators.assemblers.citySkeleton import (
    city_skeleton_from_settlement,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.application.worldData.generators.assemblers.settlementAssembler.timings import (
    SettlementAssembleTimings,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_settlement_c11_done,
    log_pack_settlement_c11_start,
    log_pack_settlement_skip_not_in_index,
    log_pack_settlement_topology_batch_done,
    log_pack_settlement_topology_batch_start,
    log_pack_settlement_topology_done,
    log_pack_settlement_topology_start,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volume_for_location,
)
from app.application.worldData.pack.read.locationsIndexRead import (
    location_uid_in_pack_index,
    location_uids_in_pack_index,
)
from app.application.worldData.settlementMapOccupancy import settlement_map_occupants
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    MaterializeBatchResult,
    MaterializeResult,
    SettlementOutdoorConflictError,
    SettlementOutdoorError,
    SettlementOutdoorNotFoundError,
    SettlementOutdoorPackMissingError,
    TopologyBatchResult,
    TopologyResult,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorPackingJob import (
    DistrictPackContext,
    SettlementOutdoorPackingJob,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    is_settlement_outdoor_target,
    packed_district_uids,
    packing_queue,
    should_skip_materialize,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import (
    SettlementOutdoorSqlPersist,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    DistrictAnchorError,
    city_graph_for_settlement,
    has_authored_non_district_children,
    load_topology_slots,
    resolve_district_uid,
    slot_for_census_row,
    topology_census,
    topology_districts,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopologyJob import (
    SettlementOutdoorTopologyJob,
)
from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    SettlementPipelineTimings,
    WallClock,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.iWorldRepository import IWorldRepository

logger = logging.getLogger(__name__)

__all__ = [
    "MaterializeBatchResult",
    "MaterializeResult",
    "SettlementOutdoorConflictError",
    "SettlementOutdoorError",
    "SettlementOutdoorNotFoundError",
    "SettlementOutdoorOrchestrator",
    "SettlementOutdoorPackMissingError",
    "TopologyBatchResult",
    "TopologyResult",
]


def _occupant_uids(world: World, locations: list[NamedLocation]) -> set[str]:
    return {
        loc.location_uid
        for loc in settlement_map_occupants(world, enumerate(locations))
    }


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
        self._library = library
        self._nodes = node_repo
        self._edges = edge_repo
        self._generator = generator
        self._topology = SettlementOutdoorTopologyJob(
            location_repo, sql_persist, generator, node_repo,
        )
        self._packing = SettlementOutdoorPackingJob(
            generator, sql_persist, self._invalidate,
        )

    def _require_pack(self, world: World) -> MapCellQueryFacade:
        facade: MapCellQueryFacade = self._facade_for(world.world_uid)
        if not facade.has_pack_for(world):
            raise SettlementOutdoorPackMissingError(
                f"World '{world.world_uid}' has no baked pack"
            )
        return facade

    def _pack_index_uids(self, world: World) -> frozenset[str]:
        return location_uids_in_pack_index(self._writer_for(world).paths)

    def _c11_targets(
        self, world: World, locations: list[NamedLocation],
    ) -> list[NamedLocation]:
        index_uids = self._pack_index_uids(world)
        return [
            loc for loc in locations
            if is_settlement_outdoor_target(loc) and loc.location_uid in index_uids
        ]

    def _skipped(
        self,
        world_uid: str,
        location_uid: str,
        clock: WallClock,
    ) -> MaterializeResult:
        setup_s = clock.total()
        return self._finish_c11(
            world_uid,
            MaterializeResult(location_uid=location_uid, status="skipped"),
            clock,
            pipeline=SettlementPipelineTimings(setup_s=setup_s),
        )

    @staticmethod
    def _finish_c11(
        world_uid: str,
        result: MaterializeResult,
        clock: WallClock,
        *,
        pipeline: SettlementPipelineTimings | None = None,
        encode_bytes: int | None = None,
    ) -> MaterializeResult:
        timings = (pipeline or SettlementPipelineTimings()).with_c11_wall(clock.total())
        result.pipeline_s = timings
        log_pack_settlement_c11_done(
            world_uid,
            location_uid=result.location_uid,
            status=result.status,
            pipeline=timings,
            districts=result.districts,
            buildings=result.buildings,
            entry_points=result.entry_points,
            encode_bytes=encode_bytes,
        )
        return result

    @staticmethod
    def _finish_topology(
        world_uid: str,
        result: TopologyResult,
        clock: WallClock,
        *,
        pipeline: SettlementPipelineTimings | None = None,
    ) -> TopologyResult:
        timings = pipeline or SettlementPipelineTimings(topology_s=clock.total())
        result.pipeline_s = timings
        log_pack_settlement_topology_done(
            world_uid,
            location_uid=result.location_uid,
            status=result.status,
            pipeline=timings,
            districts=result.districts,
            gates=result.gates,
        )
        return result

    async def plan_topology(self, world_uid: str) -> TopologyBatchResult:
        world = await self._require_world(world_uid)
        facade = self._require_pack(world)
        locs = await self._locations.list_by_world_insert_order(world_uid)
        occupant_uids = _occupant_uids(world, locs)
        targets = [
            loc for loc in locs
            if is_settlement_outdoor_target(loc) and loc.location_uid in occupant_uids
        ]
        ordered = sorted(targets, key=lambda loc: loc.location_uid)
        results: list[TopologyResult] = []
        failed: list[str] = []
        batch_t0 = log_pack_settlement_topology_batch_start(
            world_uid, settlements=len(ordered),
        )
        for loc in ordered:
            log_pack_settlement_topology_start(
                world_uid, location_uid=loc.location_uid,
            )
            clock = WallClock()
            try:
                result, pipeline = await self._topology.plan_one(world, loc, facade)
                results.append(self._finish_topology(
                    world_uid, result, clock, pipeline=pipeline,
                ))
            except Exception as exc:
                logger.exception(
                    "SettlementOutdoorOrchestrator | topology settlement=%s failed",
                    loc.location_uid,
                )
                log_pack_settlement_topology_done(
                    world_uid,
                    location_uid=loc.location_uid,
                    status="error",
                    pipeline=SettlementPipelineTimings(topology_s=clock.total()),
                )
                failed.append(loc.location_uid)
                results.append(TopologyResult(
                    location_uid=loc.location_uid,
                    status="error",
                    error=str(exc),
                ))
        log_pack_settlement_topology_batch_done(
            world_uid, settlements=len(ordered), started_at=batch_t0,
        )
        return TopologyBatchResult(results=results, failed_uids=failed)

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
                return self._skipped(world_uid, location_uid, clock)

            has_anchor = bool(district_uid) or at_x is not None or at_y is not None
            if (
                skip_if_initialized
                and not has_anchor
                and await should_skip_materialize(
                    settlement, writer, self._locations, children=children,
                )
            ):
                return self._skipped(world_uid, location_uid, clock)

            census = topology_census(children)
            if not census:
                raise SettlementOutdoorConflictError(
                    f"Location '{location_uid}' has no C23 topology census"
                )

            packed = packed_district_uids(writer, location_uid)
            try:
                if has_anchor:
                    target_uid = resolve_district_uid(
                        census,
                        district_uid=district_uid,
                        at_x=at_x,
                        at_y=at_y,
                    )
                    queue = [
                        row for row in census if row.location_uid == target_uid
                    ]
                else:
                    queue = packing_queue(census, packed)
            except DistrictAnchorError as exc:
                raise SettlementOutdoorError(str(exc)) from exc

            if has_anchor:
                target_uid = queue[0].location_uid
                if await should_skip_materialize(
                    settlement, writer, self._locations,
                    district_uid=target_uid, children=children,
                ):
                    return self._skipped(world_uid, location_uid, clock)
            elif not queue:
                return self._skipped(world_uid, location_uid, clock)

            volume = territory_volume_for_location(world, settlement)
            if volume is None:
                raise SettlementOutdoorError(
                    f"Location '{location_uid}' has no territory volume"
                )

            setup_s = clock.lap()
            terrain_cells = await facade.get_footprint_terrain(
                world,
                x0=volume.x0,
                y0=volume.y0,
                x1=volume.x1,
                y1=volume.y1,
                location_uid=location_uid,
            )
            terrain_s = clock.lap()
            library_layouts = await self._library.layouts_for_world(world)
            catalog = assemble_building_catalog(world, library_layouts)
            catalog_s = clock.lap()
            skeleton = city_skeleton_from_settlement(
                settlement,
                economic_tier=TierResolver.resolve(world=world, city=settlement),
            )
            world_nodes = await self._nodes.get_by_world(world_uid)
            world_edges = await self._edges.get_by_world(world_uid)
            frozen_slots = load_topology_slots(
                world, settlement, skeleton, topology_districts(children),
            )
            if frozen_slots is None:
                raise SettlementOutdoorConflictError(
                    f"Location '{location_uid}' has no C23 topology census"
                )
            city_graph = city_graph_for_settlement(
                world_nodes, world_edges, location_uid,
            )
            if not city_graph[0]:
                raise SettlementOutdoorConflictError(
                    f"Location '{location_uid}' has no C23 city graph"
                )
            topology_s = clock.lap()

            census_uids = [row.location_uid for row in census]
            assemble = SettlementAssembleTimings()
            buildings = 0
            levels = 0
            entry_points = 0
            generate_s = 0.0
            extract_s = 0.0
            encode_s = 0.0
            sql_s = 0.0
            publish_s = 0.0
            encode_bytes = 0
            dominant_material: str | None = None

            for row in queue:
                slot = slot_for_census_row(frozen_slots, row)
                if slot is None:
                    raise SettlementOutdoorError(
                        f"C23 slot missing for district '{row.location_uid}'"
                    )
                one, nbytes, part = await self._packing.materialize_district(
                    DistrictPackContext(
                        world=world,
                        settlement=settlement,
                        facade=facade,
                        writer=writer,
                        volume=volume,
                        terrain_cells=terrain_cells,
                        catalog=catalog,
                        city_graph=city_graph,
                        slot=slot,
                        district_uid=row.location_uid,
                        census_uids=census_uids,
                        clock=clock,
                        assemble=assemble,
                    ),
                )
                buildings += one.buildings
                levels += one.levels
                entry_points += one.entry_points
                generate_s += part.generate_s
                extract_s += part.extract_s
                encode_s += part.encode_s
                sql_s += part.sql_s
                publish_s += part.publish_s
                encode_bytes = nbytes
                dominant_material = one.dominant_material or dominant_material

            return self._finish_c11(
                world_uid,
                MaterializeResult(
                    location_uid=location_uid,
                    status="published",
                    districts=len(queue),
                    buildings=buildings,
                    levels=levels,
                    entry_points=entry_points,
                    dominant_material=dominant_material,
                ),
                clock,
                pipeline=SettlementPipelineTimings.from_parts(
                    assemble=assemble,
                    setup_s=setup_s,
                    terrain_s=terrain_s,
                    catalog_s=catalog_s,
                    topology_s=topology_s,
                    generate_s=generate_s,
                    extract_s=extract_s,
                    encode_s=encode_s,
                    sql_s=sql_s,
                    publish_s=publish_s,
                ),
                encode_bytes=encode_bytes,
            )
        except Exception:
            log_pack_settlement_c11_done(
                world_uid,
                location_uid=location_uid,
                status="error",
                pipeline=SettlementPipelineTimings(c11_s=clock.total()),
            )
            raise

    async def materialize_all(
        self, world_uid: str, *, skip_if_initialized: bool = True,
    ) -> MaterializeBatchResult:
        world = await self._require_world(world_uid)
        self._require_pack(world)
        locs = await self._locations.list_by_world_insert_order(world_uid)
        return await self._materialize_many(
            world_uid, self._c11_targets(world, locs),
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
            world_uid, self._c11_targets(world, descendants),
            skip_if_initialized=skip_if_initialized,
        )

    async def materialize_state(
        self,
        world_uid: str,
        state_uid: str,
        *,
        skip_if_initialized: bool = True,
    ) -> MaterializeBatchResult:
        world = await self._require_world(world_uid)
        self._require_pack(world)
        locs = await self._locations.list_by_state_uids(world_uid, [state_uid])
        return await self._materialize_many(
            world_uid, self._c11_targets(world, locs),
            skip_if_initialized=skip_if_initialized,
        )

    async def _materialize_many(
        self,
        world_uid: str,
        targets: list[NamedLocation],
        *,
        skip_if_initialized: bool,
    ) -> MaterializeBatchResult:
        ordered = sorted(targets, key=lambda loc: loc.location_uid)
        results: list[MaterializeResult] = []
        failed: list[str] = []
        for loc in ordered:
            try:
                result = await self.materialize(
                    world_uid,
                    loc.location_uid,
                    skip_if_initialized=skip_if_initialized,
                )
                results.append(result)
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
