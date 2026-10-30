"""Prepared and published dependencies are distinct references."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef


class SectionDependencyKind(StrEnum):
    PREPARED = "prepared"
    PUBLISHED = "published"


class PreparedSectionDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[SectionDependencyKind.PREPARED] = SectionDependencyKind.PREPARED
    section_key: SectionKey
    section_fingerprint: RevisionHex


class PublishedSectionDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[SectionDependencyKind.PUBLISHED] = SectionDependencyKind.PUBLISHED
    section_ref: SectionStateRef


type SectionDependency = Annotated[
    PreparedSectionDependency | PublishedSectionDependency, Field(discriminator="kind")
]
