"""Outdoor settlement etalon: generate → extract → C19 pack+SQL. Not DAG."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from app.application.worldData.buildingTemplateLibraryService import BuildingTemplateLibraryService
from app.application.worldData.generators.assemblers.citySkeleton import (
    city_skeleton_from_settlement,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import (
    plan_district_slots,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_side_fine,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.streets import (
    plan_city_street_grid,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.terrain import (
    column_surface,
)
from app.application.worldData.generators.assemblers.settlementAssembler.timings import (
    SettlementAssembleTimings,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.generators.coordinates import map_cell_fine_span, settlement_origin_fine
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_settlement_c11_done,
    log_pack_settlement_c11_start,
    log_pack_settlement_topology_batch_done,
    log_pack_settlement_topology_batch_start,
    log_pack_settlement_topology_done,
    log_pack_settlement_topology_start,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volume_for_location,
)
from app.application.worldData.settlementMapOccupancy import settlement_map_occupants
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    extract_settlement,
    extract_topology,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    is_settlement_outdoor_target,
    should_skip_materialize,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import (
    SettlementOutdoorSqlPersist,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    city_graph_for_settlement,
    city_nodes_for_settlement,
    has_authored_non_district_children,
    load_topology_slots,
    should_skip_topology,
    topology_districts,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTypes import (
    is_district_location,
)
from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    SettlementPipelineTimings,
    WallClock,
)
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.iWorldRepository import IWorldRepository

logger = logging.getLogger(__name__)


def _occupant_uids(world: World, locations: list[NamedLocation]) -> set[str]:
    return {
        loc.location_uid
        for loc in settlement_map_occupants(world, enumerate(locations))
    }


class SettlementOutdoorError(Exception):
    """Outdoor materialize domain error."""


class SettlementOutdoorNotFoundError(SettlementOutdoorError):
    pass


class SettlementOutdoorPackMissingError(SettlementOutdoorError):
    pass


@dataclass
class MaterializeResult:
    location_uid: str
    status: str
    districts: int = 0
    buildings: int = 0
    levels: int = 0
    entry_points: int = 0
    dominant_material: str | None = None
    error: str | None = None
    pipeline_s: SettlementPipelineTimings | None = None

    def to_dict(self) -> dict:
        payload = {
            "location_uid": self.location_uid,
            "status": self.status,
            "districts": self.districts,
            "buildings": self.buildings,
            "levels": self.levels,
            "entry_points": self.entry_points,
            "dominant_material": self.dominant_material,
        }
        if self.error:
            payload["error"] = self.error
        if self.pipeline_s is not None:
            payload["c11_pipeline"] = self.pipeline_s.as_dict()
        return payload


@dataclass
class MaterializeBatchResult:
    results: list[MaterializeResult] = field(default_factory=list)
    failed_uids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "failed_uids": self.failed_uids,
        }


@dataclass
class TopologyResult:
    location_uid: str
    status: str
    districts: int = 0
    gates: int = 0
    error: str | None = None
    pipeline_s: SettlementPipelineTimings | None = None

    def to_dict(self) -> dict:
        payload = {
            "location_uid": self.location_uid,
            "status": self.status,
            "districts": self.districts,
            "gates": self.gates,
        }
        if self.error:
            payload["error"] = self.error
        if self.pipeline_s is not None:
            payload["topology_pipeline"] = self.pipeline_s.as_dict()
        return payload


@dataclass
class TopologyBatchResult:
    results: list[TopologyResult] = field(default_factory=list)
    failed_uids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "failed_uids": self.failed_uids,
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
        self._sql = sql_persist
        self._generator = generator
        self._writer_for = writer_for
        self._facade_for = facade_for
        self._pack_context_for = pack_context_for
        self._library = library
        self._nodes = node_repo
        self._edges = edge_repo

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
        facade: MapCellQueryFacade = self._facade_for(world_uid)
        if not facade.has_pack_for(world):
            raise SettlementOutdoorPackMissingError(
                f"World '{world_uid}' has no baked pack"
            )
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
            try:
                result = await self._plan_topology_one(world, loc, facade)
                results.append(result)
            except Exception as exc:
                logger.exception(
                    "SettlementOutdoorOrchestrator | topology settlement=%s failed",
                    loc.location_uid,
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

    async def _plan_topology_one(
        self,
        world: World,
        settlement: NamedLocation,
        facade: MapCellQueryFacade,
        *,
        force: bool = False,
    ) -> TopologyResult:
        log_pack_settlement_topology_start(
            world.world_uid, location_uid=settlement.location_uid,
        )
        clock = WallClock()
        try:
            children = await self._locations.get_children(settlement.location_uid)
            world_nodes = await self._nodes.get_by_world(world.world_uid)
            settlement_nodes = city_nodes_for_settlement(
                world_nodes, settlement.location_uid,
            )
            if not force and should_skip_topology(children, settlement_nodes):
                setup_s = clock.total()
                return self._finish_topology(
                    world.world_uid,
                    TopologyResult(
                        location_uid=settlement.location_uid,
                        status="skipped",
                        districts=len(topology_districts(children)),
                    ),
                    clock,
                    pipeline=SettlementPipelineTimings(
                        setup_s=setup_s, topology_s=setup_s,
                    ),
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
            skeleton = city_skeleton_from_settlement(
                settlement,
                economic_tier=TierResolver.resolve(world=world, city=settlement),
            )
            slots = plan_district_slots(
                world, settlement, skeleton, terrain_cells or None,
            )
            topo_slots_s = clock.lap()
            origin = settlement_origin_fine(settlement)
            rng = random.Random(f"{world.world_uid}_{settlement.location_uid}")
            city_nodes, city_edges = plan_city_street_grid(
                origin.x, origin.y, origin.z,
                footprint_side_fine(world, skeleton.system_city_size),
                map_cell_fine_span(world),
                slots, world.world_uid, world, rng, skeleton,
                surface=column_surface(terrain_cells),
                settlement_uid=settlement.location_uid,
            )
            topo_streets_s = clock.lap()
            extracted = extract_topology(settlement, slots, city_nodes, city_edges)
            topo_extract_s = clock.lap()
            await self._sql.persist_topology(extracted)
            topo_sql_s = clock.lap()
            gates = sum(
                1 for node in city_nodes
                if node.node_type == ConnectionNodeType.SETTLEMENT_GATE.value
                and node.graph_level == GraphLevel.CITY.value
            )
            return self._finish_topology(
                world.world_uid,
                TopologyResult(
                    location_uid=settlement.location_uid,
                    status="planned",
                    districts=len(extracted.districts),
                    gates=gates,
                ),
                clock,
                pipeline=SettlementPipelineTimings(
                    setup_s=setup_s,
                    topo_terrain_s=topo_terrain_s,
                    topo_slots_s=topo_slots_s,
                    topo_streets_s=topo_streets_s,
                    topo_extract_s=topo_extract_s,
                    topo_sql_s=topo_sql_s,
                    topology_s=clock.total(),
                ),
            )
        except Exception:
            log_pack_settlement_topology_done(
                world.world_uid,
                location_uid=settlement.location_uid,
                status="error",
                pipeline=SettlementPipelineTimings(topology_s=clock.total()),
            )
            raise

    async def materialize(
        self,
        world_uid: str,
        location_uid: str,
        *,
        skip_if_initialized: bool = True,
    ) -> MaterializeResult:
        world = await self._require_world(world_uid)
        settlement = await self._require_settlement(world_uid, location_uid)
        declared = await self._locations.list_by_world_insert_order(world_uid)
        if settlement.location_uid not in _occupant_uids(world, declared):
            return MaterializeResult(location_uid=location_uid, status="skipped")
        facade: MapCellQueryFacade = self._facade_for(world_uid)
        if not facade.has_pack_for(world):
            raise SettlementOutdoorPackMissingError(
                f"World '{world_uid}' has no baked pack"
            )
        writer: WorldPackWriter = self._writer_for(world)
        log_pack_settlement_c11_start(world_uid, location_uid=location_uid)
        clock = WallClock()
        inner_topo: SettlementPipelineTimings | None = None
        try:
            children = await self._locations.get_children(location_uid)

            if has_authored_non_district_children(children):
                setup_s = clock.total()
                return self._finish_c11(
                    world_uid,
                    MaterializeResult(location_uid=location_uid, status="skipped"),
                    clock,
                    pipeline=SettlementPipelineTimings(setup_s=setup_s),
                )

            if skip_if_initialized and await should_skip_materialize(
                settlement, writer, self._locations,
            ):
                setup_s = clock.total()
                return self._finish_c11(
                    world_uid,
                    MaterializeResult(location_uid=location_uid, status="skipped"),
                    clock,
                    pipeline=SettlementPipelineTimings(setup_s=setup_s),
                )

            volume = territory_volume_for_location(world, settlement)
            if volume is None:
                raise SettlementOutdoorError(
                    f"Location '{location_uid}' has no territory volume"
                )

            tmp = writer.load_settlement_structure_tmp(location_uid)
            published = writer.has_published_settlement(location_uid)

            if children and not published and tmp is not None:
                writer.publish_settlement_structure(tmp, territory_volume=volume)
                self._invalidate(world, facade)
                setup_s = clock.total()
                return self._finish_c11(
                    world_uid,
                    MaterializeResult(
                        location_uid=location_uid,
                        status="recovered_publish",
                        districts=sum(
                            1 for c in children
                            if is_district_location(c.system_location_type)
                        ),
                    ),
                    clock,
                    pipeline=SettlementPipelineTimings(
                        setup_s=setup_s, publish_s=setup_s,
                    ),
                    encode_bytes=tmp.nbytes,
                )

            if not children and tmp is not None:
                tmp.tmp_path.unlink(missing_ok=True)

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
            district_rows = topology_districts(children)
            frozen_slots = load_topology_slots(
                world, settlement, skeleton, district_rows,
            ) if district_rows else None
            city_graph = None
            if frozen_slots is not None:
                city_graph = city_graph_for_settlement(
                    world_nodes, world_edges, location_uid,
                )
                if not city_graph[0]:
                    frozen_slots = None
                    city_graph = None
            if frozen_slots is None:
                topo_result = await self._plan_topology_one(
                    world, settlement, facade,
                    force=bool(district_rows),
                )
                inner_topo = topo_result.pipeline_s
                children = await self._locations.get_children(location_uid)
                world_nodes = await self._nodes.get_by_world(world_uid)
                world_edges = await self._edges.get_by_world(world_uid)
                frozen_slots = load_topology_slots(
                    world, settlement, skeleton, topology_districts(children),
                )
                if frozen_slots is not None:
                    city_graph = city_graph_for_settlement(
                        world_nodes, world_edges, location_uid,
                    )
            topology_s = clock.lap()
            assemble = SettlementAssembleTimings()
            layout = self._generator.generate_layout(
                world, settlement, terrain_cells or None, catalog=catalog,
                district_slots=frozen_slots,
                city_graph=city_graph,
                timings=assemble,
            )
            generate_s = clock.lap()
            extracted = extract_settlement(settlement, layout)
            extract_s = clock.lap()
            tmp_ref = writer.encode_settlement_structure_tmp(location_uid, extracted.wire)
            encode_s = clock.lap()
            await self._sql.persist(extracted)
            sql_s = clock.lap()
            writer.publish_settlement_structure(tmp_ref, territory_volume=volume)
            self._invalidate(world, facade)
            publish_s = clock.lap()
            return self._finish_c11(
                world_uid,
                MaterializeResult(
                    location_uid=location_uid,
                    status="published",
                    districts=len(extracted.districts),
                    buildings=len(extracted.buildings),
                    levels=len(extracted.levels),
                    entry_points=len(extracted.entry_points),
                    dominant_material=layout.dominant_material,
                ),
                clock,
                pipeline=SettlementPipelineTimings.from_parts(
                    assemble=assemble,
                    topology=inner_topo,
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
                encode_bytes=tmp_ref.nbytes,
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
        locs = await self._locations.list_by_world_insert_order(world_uid)
        occupant_uids = _occupant_uids(world, locs)
        targets = [
            loc for loc in locs
            if is_settlement_outdoor_target(loc) and loc.location_uid in occupant_uids
        ]
        return await self._materialize_many(
            world_uid, targets, skip_if_initialized=skip_if_initialized,
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
        declared = await self._locations.list_by_world_insert_order(world_uid)
        occupant_uids = _occupant_uids(world, declared)
        descendants = await self._locations.list_descendants(ancestor_uid)
        targets = [
            loc for loc in descendants
            if is_settlement_outdoor_target(loc) and loc.location_uid in occupant_uids
        ]
        return await self._materialize_many(
            world_uid, targets, skip_if_initialized=skip_if_initialized,
        )

    async def materialize_state(
        self,
        world_uid: str,
        state_uid: str,
        *,
        skip_if_initialized: bool = True,
    ) -> MaterializeBatchResult:
        world = await self._require_world(world_uid)
        declared = await self._locations.list_by_world_insert_order(world_uid)
        occupant_uids = _occupant_uids(world, declared)
        locs = await self._locations.list_by_state_uids(world_uid, [state_uid])
        targets = [
            loc for loc in locs
            if is_settlement_outdoor_target(loc) and loc.location_uid in occupant_uids
        ]
        return await self._materialize_many(
            world_uid, targets, skip_if_initialized=skip_if_initialized,
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
