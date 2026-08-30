"""One SQL transaction for outdoor etalon tree + road graph. No pack I/O."""

from __future__ import annotations

from app.application.worldData.connectionPersistService import ConnectionPersistService
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    ExtractedSettlement,
)
from app.db.database import Database
from app.db.repositories.iLocationEntryPointRepository import ILocationEntryPointRepository
from app.db.repositories.iLocationLevelRepository import ILocationLevelRepository
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository


class SettlementOutdoorSqlPersist:

    def __init__(
        self,
        db: Database,
        location_repo: INamedLocationRepository,
        level_repo: ILocationLevelRepository,
        entry_repo: ILocationEntryPointRepository,
        connection_persist: ConnectionPersistService,
    ) -> None:
        self._db = db
        self._locations = location_repo
        self._levels = level_repo
        self._entries = entry_repo
        self._connections = connection_persist

    async def persist(self, extracted: ExtractedSettlement) -> None:
        async with self._db.transaction():
            await self._locations.upsert_bulk(
                [*extracted.districts, *extracted.buildings],
            )
            await self._levels.upsert_bulk(extracted.levels)
            await self._entries.upsert_bulk(extracted.entry_points)
            await self._connections.persist_graph(
                extracted.nodes, extracted.edges, [],
            )
