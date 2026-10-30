"""Patch addresses and immutable preparation metadata, without domain payload."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.values import FormatVersion, PatchOrdinal


class PatchRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    operation_id: EntityUid
    section_key: SectionKey
    ordinal: PatchOrdinal


class PatchHeader(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    ref: PatchRef
    format_version: FormatVersion
    depends_on: tuple[PatchRef, ...]
    artifacts: tuple[ArtifactRef, ...]

    @model_validator(mode="after")
    def unique_references(self) -> Self:
        if self.ref in self.depends_on:
            raise ValueError("patch cannot depend on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("duplicate patch dependency")
        if len(set(self.artifacts)) != len(self.artifacts):
            raise ValueError("duplicate artifact reference")
        return self
