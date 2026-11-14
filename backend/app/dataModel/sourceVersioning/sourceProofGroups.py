"""Ordered group correlation values; no union, subset or matching algorithm."""

# TODO(SOURCE-TYPED-ERRORS): Migrate the manual ValueError diagnostics below to
# the agreed Source typed-error contract; independent failures need aggregation.
# This transition and its acceptance criterion remain OPEN.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

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
