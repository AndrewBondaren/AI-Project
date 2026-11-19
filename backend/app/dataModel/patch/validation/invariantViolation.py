"""Internal location of a fact, without presentation field paths."""

from typing import Annotated, Self
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from app.dataModel.patch.validation.invariantDetails import PatchSetInvariantCode, PatchSetInvariantDetails


class PatchSetInvariantViolation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    details: PatchSetInvariantDetails
    section_index: Annotated[StrictInt, Field(ge=0)] | None = None
    patch_index: Annotated[StrictInt, Field(ge=0)] | None = None
    dependency_index: Annotated[StrictInt, Field(ge=0)] | None = None
    player_index: Annotated[StrictInt, Field(ge=0)] | None = None
    related_index: Annotated[StrictInt, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def coherent_location(self) -> Self:
        expected = {
            PatchSetInvariantCode.WORLD_MISMATCH: (False, False, False, False, False),
            PatchSetInvariantCode.MISSING_PACK: (False, False, False, False, False),
            PatchSetInvariantCode.DUPLICATE_PLAYER: (False, False, False, True, True),
            PatchSetInvariantCode.DUPLICATE_SECTION: (True, False, False, False, True),
            PatchSetInvariantCode.MISSING_PREPARED_DEPENDENCY: (True, False, True, False, False),
            PatchSetInvariantCode.PREPARED_DEPENDENCY_ORDER: (True, False, True, False, True),
            PatchSetInvariantCode.PATCH_OPERATION_MISMATCH: (True, True, False, False, False),
            PatchSetInvariantCode.PATCH_SECTION_MISMATCH: (True, True, False, False, False),
            PatchSetInvariantCode.DUPLICATE_PATCH_ORDINAL: (True, True, False, False, True),
        }[self.details.code]
        actual = tuple(value is not None for value in (
            self.section_index, self.patch_index, self.dependency_index, self.player_index, self.related_index,
        ))
        if actual != expected:
            raise ValueError("indices do not describe this invariant reason")
        return self
