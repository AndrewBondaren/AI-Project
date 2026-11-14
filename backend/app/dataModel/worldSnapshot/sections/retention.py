"""Exact immutable state/history artifact closures; no storage effects."""
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef


class SectionStateRetention(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    state: SectionStateRef
    artifacts: tuple[ArtifactRef, ...]

    @model_validator(mode="after")
    def unique_artifacts(self) -> Self:
        if len(set(self.artifacts)) != len(self.artifacts):
            raise ValueError("duplicate state artifact")
        return self


class SectionHistoryRetention(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    history: SectionHistoryRef
    artifacts: tuple[ArtifactRef, ...]

    @model_validator(mode="after")
    def unique_artifacts(self) -> Self:
        if len(set(self.artifacts)) != len(self.artifacts):
            raise ValueError("duplicate history artifact")
        return self
