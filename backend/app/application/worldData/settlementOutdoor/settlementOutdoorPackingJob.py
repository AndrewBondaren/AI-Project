"""Internal C24 district packing job — generate one district, extract, C19 publish.

Not a public orchestrator. Facade owns gates, census, packing queue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.application.worldData.buildingTemplateLibraryService import (
    BuildingTemplateLibraryService,
)
from app.application.worldData.generators.assemblers.citySkeleton import (
    city_skeleton_from_settlement,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.generators.assemblers.settlementAssembler.timings import (
    SettlementAssembleTimings,
)
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volume_for_location,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    MaterializeResult,
    SettlementOutdoorConflictError,
    SettlementOutdoorError,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    PACKING_GRAPH_LEVELS,
    extract_settlement,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    packed_district_uids,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import (
    SettlementOutdoorSqlPersist,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    city_graph_for_settlement,
    load_topology_slots,
    slot_for_census_row,
    topology_census,
    topology_districts,
)
from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    SettlementPipelineTimings,
    WallClock,
)
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.worldPack.settlementStructureStatus import (
    settlement_structure_status_for,
)
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository


@dataclass
class DistrictPackContext:
    world: World
    settlement: NamedLocation
    facade: MapCellQueryFacade
    writer: WorldPackWriter
    volume: TerritoryVolume
    terrain_cells: list[MapCell] | None
    catalog: BuildingCatalog
    city_graph: tuple[list[ConnectionNode], list[ConnectionEdge]]
    slot: DistrictSlot
    district_uid: str
    census_uids: list[str]
    clock: WallClock
    assemble: SettlementAssembleTimings


class SettlementOutdoorPackingJob:

    def __init__(
        self,
        generator: SettlementGeneratorService,
        sql_persist: SettlementOutdoorSqlPersist,
        invalidate: Callable[[World, MapCellQueryFacade], None],
        library: BuildingTemplateLibraryService,
        node_repo: IConnectionNodeRepository,
        edge_repo: IConnectionEdgeRepository,
    ) -> None:
        self._generator = generator
        self._sql = sql_persist
        self._invalidate = invalidate
        self._library = library
        self._nodes = node_repo
        self._edges = edge_repo

    async def run_queue(
        self,
        world: World,
        settlement: NamedLocation,
        facade: MapCellQueryFacade,
        writer: WorldPackWriter,
        children: list[NamedLocation],
        queue: list[NamedLocation],
        clock: WallClock,
    ) -> tuple[MaterializeResult, int, SettlementPipelineTimings]:
        location_uid = settlement.location_uid
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
        world_nodes = await self._nodes.get_by_world(world.world_uid)
        world_edges = await self._edges.get_by_world(world.world_uid)
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

        census_uids = [row.location_uid for row in topology_census(children)]
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
            one, nbytes, part = await self.materialize_district(
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

        return (
            MaterializeResult(
                location_uid=location_uid,
                status="published",
                districts=len(queue),
                buildings=buildings,
                levels=levels,
                entry_points=entry_points,
                dominant_material=dominant_material,
            ),
            encode_bytes,
            SettlementPipelineTimings.from_parts(
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
        )


    async def materialize_district(
        self,
        ctx: DistrictPackContext,
    ) -> tuple[MaterializeResult, int, SettlementPipelineTimings]:
        location_uid = ctx.settlement.location_uid
        layout = self._generator.generate_layout(
            ctx.world, ctx.settlement, ctx.terrain_cells or None,
            catalog=ctx.catalog,
            district_slots=[ctx.slot],
            city_graph=ctx.city_graph,
            timings=ctx.assemble,
        )
        generate_s = ctx.clock.lap()
        extracted = extract_settlement(
            ctx.settlement, layout, graph_levels=PACKING_GRAPH_LEVELS,
        )
        if (
            not extracted.districts
            or extracted.districts[0].location_uid != ctx.district_uid
        ):
            raise SettlementOutdoorError(
                f"extract district uid mismatch for '{ctx.district_uid}'"
            )
        extract_s = ctx.clock.lap()
        tmp_ref = ctx.writer.encode_settlement_structure_tmp(
            location_uid, extracted.wire,
        )
        encode_s = ctx.clock.lap()
        await self._sql.persist(extracted)
        sql_s = ctx.clock.lap()
        packed = packed_district_uids(ctx.writer, location_uid)
        if ctx.district_uid not in packed:
            packed = [*packed, ctx.district_uid]
        status = settlement_structure_status_for(
            packed, ctx.census_uids, has_file=True,
        )
        ctx.writer.publish_settlement_structure(
            tmp_ref,
            territory_volume=ctx.volume,
            packed_district_uids=packed,
            structure_status=status,
        )
        self._invalidate(ctx.world, ctx.facade)
        publish_s = ctx.clock.lap()
        return (
            MaterializeResult(
                location_uid=location_uid,
                status="published",
                districts=1,
                buildings=len(extracted.buildings),
                levels=len(extracted.levels),
                entry_points=len(extracted.entry_points),
                dominant_material=layout.dominant_material,
            ),
            tmp_ref.nbytes,
            SettlementPipelineTimings(
                generate_s=generate_s,
                extract_s=extract_s,
                encode_s=encode_s,
                sql_s=sql_s,
                publish_s=publish_s,
            ),
        )
