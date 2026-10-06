"""One SQL transaction for outdoor etalon tree + road graph. No pack I/O."""

from __future__ import annotations

from collections.abc import Callable

from app.application.worldData.connectionPersistService import ConnectionPersistService
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    ExtractedSettlement,
    ExtractedTopology,
)
from app.db.database import Database
from app.db.repositories.iTransitionRepository import ITransitionRepository, TransitionRepositoryContext
from app.db.repositories.iLocationLevelRepository import ILocationLevelRepository
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository


class SettlementOutdoorSqlPersist:

    def __init__(
        self,
        db: Database,
        location_repo: INamedLocationRepository,
        level_repo: ILocationLevelRepository,
        transition_repo_for: Callable[[TransitionRepositoryContext], ITransitionRepository],
        connection_persist: ConnectionPersistService,
    ) -> None:
        self._db = db
        self._locations = location_repo
        self._levels = level_repo
        self._transition_repo_for = transition_repo_for
        self._connections = connection_persist

    async def persist(self, extracted: ExtractedSettlement) -> None:
        async with self._db.transaction():
            await self._locations.upsert_bulk(
                [*extracted.districts, *extracted.buildings],
            )
            await self._levels.upsert_bulk(extracted.levels)
            await self._connections.persist_graph(
                extracted.nodes, extracted.edges, [],
            )
            await self._persist_transitions(extracted)

    async def persist_topology(self, extracted: ExtractedTopology) -> None:
        async with self._db.transaction():
            await self._locations.upsert_bulk(extracted.districts)
            await self._connections.persist_graph(
                extracted.nodes, extracted.edges, [],
            )
            await self._persist_transitions(extracted)

    async def _persist_transitions(self, extracted: ExtractedSettlement | ExtractedTopology) -> None:
        if not extracted.sql_transitions:
            return
        if extracted.transition_context is None:
            raise ValueError("transition reference context required")
        repo = self._transition_repo_for(extracted.transition_context)
        # Reconciliation is deferred: retain existing aggregates and their CRUD state.
        missing = []
        for item in extracted.sql_transitions:
            if await repo.get(item.transition_uid) is None:
                missing.append(item)
        await repo.upsert_bulk(missing)
