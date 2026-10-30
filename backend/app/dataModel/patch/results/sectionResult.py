"""Domain validation and apply receipts do not assert a durable commit."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef


class SectionAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")


class SectionRefused(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    category: SnapshotApplyOutcomeKind
    diagnostics: tuple[FieldPathError, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def refusal_category(self) -> Self:
        if self.category is SnapshotApplyOutcomeKind.COMMITTED:
            raise ValueError("section refusal cannot be committed")
        return self


type SectionValidation = SectionAccepted | SectionRefused


class SectionApplyReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    section_key: SectionKey
    history_refs: tuple[SectionHistoryRef, ...]
    state_refs: tuple[SectionStateRef, ...]
    changed: tuple[PatchRef, ...]
    retained_artifacts: tuple[ArtifactRef, ...]

    @model_validator(mode="after")
    def coherent_references(self) -> Self:
        for refs in (self.history_refs, self.state_refs):
            chains = tuple((ref.snapshot.kind, ref.snapshot.world_uid, ref.snapshot.timeline_id)
                           if isinstance(ref.snapshot, WorldSnapshotRef) else
                           (ref.snapshot.kind, ref.snapshot.player_uid)
                           for ref in refs)
            if len(set(chains)) != len(chains):
                raise ValueError("duplicate section reference for a snapshot chain")
            if any(ref.section_key != self.section_key for ref in refs):
                raise ValueError("receipt reference belongs to another section")
        if any(ref.section_key != self.section_key for ref in self.changed):
            raise ValueError("changed patch belongs to another section")
        if len(set(self.changed)) != len(self.changed):
            raise ValueError("duplicate changed patch")
        if len(set(self.retained_artifacts)) != len(self.retained_artifacts):
            raise ValueError("duplicate retained artifact")
        return self
