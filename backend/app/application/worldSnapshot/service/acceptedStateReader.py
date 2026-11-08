"""Resolve an accepted publication or immutable snapshot within the caller's read scope."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope
from app.application.worldSnapshot.storage.historyStore import ISnapshotHistoryStore
from app.application.worldSnapshot.storage.publicationStore import IExactWorldPublicationReader
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef


class StateReadFailure(Enum):
    MISSING_PUBLICATION = auto()
    GAMEPLAY_NOT_STARTED = auto()
    MISSING_SNAPSHOT = auto()
    MISSING_SECTION = auto()


@dataclass(frozen=True)
class PublicationMismatch:
    observed: WorldPublicationRef


type SnapshotResolution = SectionStateRef | Literal[StateReadFailure.MISSING_SNAPSHOT, StateReadFailure.MISSING_SECTION]
type PublicationResolution = WorldPublicationRef | SectionStateRef | StateReadFailure | PublicationMismatch


class AcceptedStateReader:
    def __init__(self, publications: IExactWorldPublicationReader, history: ISnapshotHistoryStore):
        self._publications = publications
        self._history = history

    async def resolve_publication(self, publication: WorldPublicationRef, key: SectionKey,
                                  scope: CommitReadScope) -> PublicationResolution:
        observed = await self._publications.read_exact(publication.world_uid, publication.publication_id, scope=scope)
        if observed is None:
            return StateReadFailure.MISSING_PUBLICATION
        if observed != publication:
            return PublicationMismatch(observed)
        if not observed.gameplay_started:
            return StateReadFailure.GAMEPLAY_NOT_STARTED
        head = observed.snapshot_head
        if head is None or head.timeline_id != observed.active_timeline_id:
            return observed
        return await self.resolve_snapshot(head, key, scope)

    async def resolve_snapshot(self, snapshot: WorldSnapshotRef, key: SectionKey,
                               scope: CommitReadScope) -> SnapshotResolution:
        metadata = await self._history.read(snapshot, scope=scope)
        if metadata is None:
            return StateReadFailure.MISSING_SNAPSHOT
        if not isinstance(metadata, WorldSnapshotMetadata) or metadata.ref != snapshot:
            raise PublicationInfrastructureError("history returned metadata for another snapshot")
        for state in metadata.state_refs:
            if state.section_key == key:
                owner = state.snapshot
                if (not isinstance(owner, WorldSnapshotRef) or owner.world_uid != snapshot.world_uid
                        or owner.timeline_id != snapshot.timeline_id):
                    raise PublicationInfrastructureError("state belongs to another world or timeline")
                return state
        return StateReadFailure.MISSING_SECTION
