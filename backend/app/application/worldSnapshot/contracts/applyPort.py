"""The sole runtime publication entry; implementations belong to Snapshot application."""

from typing import Protocol
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult


class IWorldSnapshotApply(Protocol):
    async def apply[S: DomainSection](self, patch_set: PatchSet[S]) -> SnapshotApplyResult: ...
