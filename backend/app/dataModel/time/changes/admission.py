"""Read structurally valid operands without suppressing sibling diagnostics."""
from typing import cast

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef


def json_collections(value: object) -> object:
    """Keep JSON arrays admissible after a wrap materializes immutable records."""
    if isinstance(value, list):
        return tuple(json_collections(item) for item in value)
    if isinstance(value, dict):
        return {key: json_collections(item) for key, item in value.items()}
    return value


def raw_field[M: BaseModel, T](value: object, field: FieldRef[M, T]) -> object:
    name = bind_field(field).field
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def valid_field[M: BaseModel, T](value: object, field: FieldRef[M, T]) -> T | None:
    bound = bind_field(field)
    try:
        return cast(T, TypeAdapter(bound.model.model_fields[bound.field].rebuild_annotation()).validate_python(
            raw_field(value, field), strict=True))
    except ValidationError:
        return None
