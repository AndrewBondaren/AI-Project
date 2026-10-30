"""Typed section envelopes; concrete operation unions belong to their domains."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.sections.dependency import PreparedSectionDependency, SectionDependency
from app.dataModel.patch.values import FormatVersion


class SectionHeader(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    key: SectionKey
    format_version: FormatVersion
    depends_on: tuple[SectionDependency, ...]

    @model_validator(mode="after")
    def unique_dependencies(self) -> Self:
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("duplicate section dependency")
        if any(isinstance(dep, PreparedSectionDependency) and dep.section_key == self.key
               for dep in self.depends_on):
            raise ValueError("section cannot depend on its own prepared result")
        return self


class DomainSection[P: BaseModel](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    header: SectionHeader
    patches: tuple[P, ...] = Field(min_length=1)
