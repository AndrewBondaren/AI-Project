from contextlib import AbstractAsyncContextManager
from typing import Protocol

from app.application.worldSnapshot.contracts.commitScope import CommitReadScope
from app.application.worldSnapshot.service.acceptedStateReader import AcceptedStateReader, StateReadFailure
from app.dataModel.identity.uid import EntityUid
from app.dataModel.time.reads.capture import HistoricalTimeCapture, TimeCapture
from app.dataModel.time.reads.request import CurrentTimeRead, HistoricalTimeRead
from app.dataModel.time.results.errors import (
    TimeInactiveTimeline, TimePublicationConflict, TimeStateUnavailable, TimeUnavailableReason,
)
from app.dataModel.time.storage.state import CLOCK_SECTION, PublicationTimeState, StoredTimeState
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef


class ReadScopes(Protocol):
    def read_scope(self) -> AbstractAsyncContextManager[CommitReadScope]: ...


class CurrentPublications(Protocol):
    async def read_current_if_world_exists(self, world_uid: EntityUid, scope: CommitReadScope) -> WorldPublicationRef | None: ...


class TimePayloads(Protocol):
    async def read_binding(self, publication: WorldPublicationRef, scope: CommitReadScope) -> PublicationTimeState | None: ...
    async def read_section(self, ref: SectionStateRef, scope: CommitReadScope) -> StoredTimeState | None: ...


class SnapshotTimeReadSource:
    def __init__(self, scopes: ReadScopes, publications: CurrentPublications, accepted: AcceptedStateReader,
                 payloads: TimePayloads):
        self._scopes = scopes
        self._publications = publications
        self._accepted = accepted
        self._payloads = payloads

    async def _capture(self, publication: WorldPublicationRef, scope: CommitReadScope) -> TimeCapture | TimeStateUnavailable:
        address = await self._accepted.resolve_publication(publication, CLOCK_SECTION, scope)
        reason = TimeUnavailableReason.SOURCE_UNRESOLVED
        if isinstance(address, WorldPublicationRef):
            binding = await self._payloads.read_binding(address, scope)
            if binding is not None:
                return TimeCapture(publication=address, point=binding.state.point)
        elif isinstance(address, SectionStateRef):
            payload = await self._payloads.read_section(address, scope)
            if payload is not None:
                return TimeCapture(publication=publication, point=payload.state.point)
        elif address == StateReadFailure.GAMEPLAY_NOT_STARTED:
            reason = TimeUnavailableReason.CLOCK_UNINITIALIZED
        return TimeStateUnavailable(world_uid=publication.world_uid, reason=reason)

    async def read_pinned(self, publication: WorldPublicationRef):
        async with self._scopes.read_scope() as scope:
            return await self._capture(publication, scope)

    async def read_current(self, request: CurrentTimeRead):
        expected = request.expected
        async with self._scopes.read_scope() as scope:
            observed = await self._publications.read_current_if_world_exists(expected.world_uid, scope)
            if observed is None:
                return TimeStateUnavailable(world_uid=expected.world_uid, reason=TimeUnavailableReason.WORLD_MISSING)
            if expected.active_timeline_id is not None and expected.active_timeline_id != observed.active_timeline_id:
                return TimeInactiveTimeline(requested=expected.active_timeline_id, active=observed.active_timeline_id)
            if expected != observed:
                return TimePublicationConflict(expected=expected, observed=observed)
            return await self._capture(observed, scope)

    async def read_historical(self, request: HistoricalTimeRead):
        snapshot = request.snapshot
        async with self._scopes.read_scope() as scope:
            address = await self._accepted.resolve_snapshot(snapshot, CLOCK_SECTION, scope)
            reason = TimeUnavailableReason.SOURCE_UNRESOLVED
            if isinstance(address, SectionStateRef):
                payload = await self._payloads.read_section(address, scope)
                if payload is not None:
                    return HistoricalTimeCapture(snapshot=snapshot, point=payload.state.point)
            elif address == StateReadFailure.MISSING_SNAPSHOT:
                reason = TimeUnavailableReason.SNAPSHOT_MISSING
            return TimeStateUnavailable(world_uid=snapshot.world_uid, reason=reason)
