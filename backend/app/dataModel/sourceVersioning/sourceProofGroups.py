"""Ordered group correlation values; no union, subset or matching algorithm."""

from typing import Self

from pydantic import Field, model_validator

from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.sourceVersioning.sourceProofResult import SourceProofResult
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection


class SourceProofGroupsInput(SourceValue, frozen=True):
    groups: tuple[SourceProofInput, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def same_world(self) -> Self:
        world = self.groups[0].world_uid
        if any(group.world_uid != world for group in self.groups):
            raise ValueError("groups must belong to one world")
        return self


class SourceProofGroupsResult(SourceValue, frozen=True):
    admission: SourceProofResult
    selections: tuple[SourceProofSelection, ...] = Field(min_length=1)
