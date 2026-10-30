"""Common publication CAS ports; reads do not initialize or publish state."""

from typing import Protocol
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.identity.uid import EntityUid
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef
from app.dataModel.worldSnapshot.results.publication import CasDecision


class IWorldPublicationStore(Protocol):
    async def read(self, world_uid: EntityUid, *, scope: CommitReadScope | None = None) -> WorldPublicationRef: ...

    async def compare_append(self, scope: CommitScope, expected: WorldPublicationRef,
                             next_publication: WorldPublicationRef) -> CasDecision: ...


class IPlayerPublicationStore(Protocol):
    async def read(self, player_uid: EntityUid, *, scope: CommitReadScope | None = None) -> PlayerSnapshotRef | None: ...

    async def compare_append(self, scope: CommitScope, expected: PlayerHeadExpectation,
                             next_ref: PlayerSnapshotRef, operation_id: EntityUid) -> CasDecision: ...


class IWorldPublicationInitializer(Protocol):
    async def initialize(self, scope: CommitScope, world_uid: EntityUid) -> WorldPublicationRef:
        """Explicit bootstrap capability; unavailable to a domain handler."""
        ...
