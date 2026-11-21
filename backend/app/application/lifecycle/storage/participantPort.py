"""Own Lifecycle reads and borrowed transaction writer; no commit authority."""
from typing import Protocol
from pydantic import BaseModel

from app.application.worldSnapshot.contracts.commitScope import CommitReadScope
from app.dataModel.lifecycle.publication.appendResult import LifecycleAppended
from app.dataModel.lifecycle.storage.acceptedChanges import AcceptedChangesQuery
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.patch.results.sectionResult import SectionRefused
from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyIssue


class ILifecycleAcceptedChangesReader[Result: BaseModel](Protocol):
    async def lookup_accepted_changes(
        self, request: AcceptedChangesQuery, *, scope: CommitReadScope,
    ) -> Result: ...


class ILifecycleParticipantReader[L: BaseModel, Capture: BaseModel](Protocol):
    async def read_for_section(
        self, section: L, *, publication: WorldPublicationRef, scope: CommitReadScope,
    ) -> tuple[Capture, ...]: ...


class ILifecycleParticipantWriter[L: BaseModel, Refusal: SectionRefused[LifecycleApplyIssue]](Protocol):
    async def append(
        self, section: L, *, expected: WorldPublicationRef, target: WorldSnapshotRef,
    ) -> LifecycleAppended | Refusal: ...
