"""Internal C24 district packing job — generate one district, extract, C19 publish.

Not a public orchestrator. Facade owns gates, census, packing queue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.generators.assemblers.settlementAssembler.timings import (
    SettlementAssembleTimings,
)
from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    MaterializeResult,
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
    ) -> None:
        self._generator = generator
        self._sql = sql_persist
        self._invalidate = invalidate

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
