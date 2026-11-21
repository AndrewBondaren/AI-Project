"""The sole runtime publication entry; implementations belong to Snapshot application."""

from typing import Protocol
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult


class IWorldSnapshotApply[S: DomainSection, T: SnapshotApplyResult](Protocol):
    async def apply(self, patch_set: PatchSet[S]) -> T: ...
