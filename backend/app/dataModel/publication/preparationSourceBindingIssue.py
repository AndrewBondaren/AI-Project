"""Pure relation diagnostics, distinct from current storage/hold failures."""
from enum import StrEnum

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class PreparationSourceBindingFieldCode(StrEnum):
    WORLD_MISMATCH = "world_mismatch"
    DUPLICATE_SOURCE = "duplicate_source"
    INVALID_SOURCE_HOLDER = "invalid_source_holder"


class PreparationSourceBindingFieldIssue(FieldPathError[PreparationSourceBindingFieldCode]):
    """Binding relation failure at an exact typed field path."""
