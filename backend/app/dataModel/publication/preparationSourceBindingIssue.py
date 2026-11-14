"""Pure relation diagnostics, distinct from current storage/hold failures."""
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PreparationSourceBindingFieldCode(StrEnum):
    INVALID_SHAPE = "invalid_shape"
    WORLD_MISMATCH = "world_mismatch"
    DUPLICATE_SOURCE = "duplicate_source"
    INVALID_SOURCE_HOLDER = "invalid_source_holder"


class PreparationSourceBindingFieldIssue(FieldPathError[PreparationSourceBindingFieldCode]):
    """Binding relation failure at an exact typed field path."""


class PreparationSourceBindingShapeIssue(BaseModel, frozen=True):
    """Exact structural location when no declared field path exists."""
    model_config = ConfigDict(strict=True, extra="forbid", revalidate_instances="always")

    code: Literal[PreparationSourceBindingFieldCode.INVALID_SHAPE]
    location: tuple[StrictStr | StrictInt, ...]
    message: StrictStr


type PreparationSourceBindingIssue = PreparationSourceBindingFieldIssue | PreparationSourceBindingShapeIssue
