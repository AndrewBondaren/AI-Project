"""Outdoor settlement etalon: generate → extract → C19 pack+SQL. Not DAG."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volume_for_location,
)
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    extract_settlement,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    is_settlement_outdoor_target,
    should_skip_materialize,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSqlPersist import (
    SettlementOutdoorSqlPersist,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.iWorldRepository import IWorldRepository

logger = logging.getLogger(__name__)


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
    ) -> None:
        self._worlds = world_repo
        self._locations = location_repo
        self._sql = sql_persist
        self._generator = generator
        self._writer_for = writer_for
        self._facade_for = facade_for
        self._pack_context_for = pack_context_for

    async def materialize(
        self,
        world_uid: str,
        location_uid: str,
        *,
        skip_if_initialized: bool = True,
    ) -> MaterializeResult:
        world = await self._require_world(world_uid)
        settlement = await self._require_settlement(world_uid, location_uid)
        facade: MapCellQueryFacade = self._facade_for(world_uid)
        if not facade.has_pack_for(world):
            raise SettlementOutdoorPackMissingError(
                f"World '{world_uid}' has no baked pack"
            )
        writer: WorldPackWriter = self._writer_for(world)
        children = await self._locations.get_children(location_uid)

        if skip_if_initialized and await should_skip_materialize(
            settlement, writer, self._locations,
        ):
            logger.info(
                "SettlementOutdoorOrchestrator | settlement=%s skipped C14",
                location_uid,
            )
            return MaterializeResult(location_uid=location_uid, status="skipped")

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
            logger.info(
                "SettlementOutdoorOrchestrator | settlement=%s recovered publish",
                location_uid,
            )
            district_type = WorldLocationTypeRegistry.canonical_engine().entry_for("district")
            district_key = district_type.system_type if district_type is not None else None
            return MaterializeResult(
                location_uid=location_uid,
                status="recovered_publish",
                districts=sum(
                    1 for c in children
                    if district_key is not None and c.system_location_type == district_key
                ),
            )

        if not children and tmp is not None:
            tmp.tmp_path.unlink(missing_ok=True)

        terrain_cells = await facade.get_footprint_terrain(
            world,
            x0=volume.x0,
            y0=volume.y0,
            x1=volume.x1,
            y1=volume.y1,
            location_uid=location_uid,
        )
        layout = self._generator.generate_layout(
            world, settlement, terrain_cells or None,
        )
        extracted = extract_settlement(settlement, layout)
        tmp_ref = writer.encode_settlement_structure_tmp(location_uid, extracted.wire)
        await self._sql.persist(extracted)
        writer.publish_settlement_structure(tmp_ref, territory_volume=volume)
        self._invalidate(world, facade)
        logger.info(
            "SettlementOutdoorOrchestrator | settlement=%s published "
            "districts=%d buildings=%d entries=%d",
            location_uid,
            len(extracted.districts),
            len(extracted.buildings),
            len(extracted.entry_points),
        )
        return MaterializeResult(
            location_uid=location_uid,
            status="published",
            districts=len(extracted.districts),
            buildings=len(extracted.buildings),
            levels=len(extracted.levels),
            entry_points=len(extracted.entry_points),
            dominant_material=layout.dominant_material,
        )

    async def materialize_all(
        self, world_uid: str, *, skip_if_initialized: bool = True,
    ) -> MaterializeBatchResult:
        await self._require_world(world_uid)
        locs = await self._locations.get_by_world(world_uid)
        targets = [loc for loc in locs if is_settlement_outdoor_target(loc)]
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
        await self._require_world(world_uid)
        ancestor = await self._locations.get_by_id(ancestor_uid)
        if ancestor is None or ancestor.world_uid != world_uid:
            raise SettlementOutdoorNotFoundError(
                f"Location '{ancestor_uid}' not found"
            )
        descendants = await self._locations.list_descendants(ancestor_uid)
        targets = [loc for loc in descendants if is_settlement_outdoor_target(loc)]
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
        await self._require_world(world_uid)
        locs = await self._locations.list_by_state_uids(world_uid, [state_uid])
        targets = [loc for loc in locs if is_settlement_outdoor_target(loc)]
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
