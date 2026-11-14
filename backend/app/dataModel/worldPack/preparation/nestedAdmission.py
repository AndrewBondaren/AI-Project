"""Strict Pack admission of existing metadata records before owning normalization."""

from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_core import InitErrorDetails

from app.dataModel.validation.immutableValue import validate_immutable

RecordT = TypeVar("RecordT", bound=BaseModel)


@lru_cache
def _field_adapter(model: type[BaseModel], name: str) -> TypeAdapter:
    return TypeAdapter(model.model_fields[name].rebuild_annotation())


def strict_metadata_record(model: type[RecordT], value: object) -> RecordT:
    """Check actual fields, including forged instances, without a mirror schema."""
    if isinstance(value, model):
        raw = dict(vars(value))
        raw.update(value.model_extra or {})
    elif isinstance(value, dict):
        raw = value
    else:
        return model.model_validate(value, strict=True)

    errors: list[InitErrorDetails] = []
    checked: dict[str, object] = {}
    for name, field in model.model_fields.items():
        if name not in raw:
            errors.append({"type": "missing", "loc": (name,), "input": raw})
            continue
        child = raw[name]
        try:
            annotation = field.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                checked[name] = strict_metadata_record(annotation, child)
            else:
                checked[name] = _field_adapter(model, name).validate_python(child, strict=True)
        except ValidationError as exc:
            for error in exc.errors(include_url=False):
                detail: InitErrorDetails = {
                    "type": error["type"], "loc": (name, *error["loc"]), "input": error["input"],
                }
                if "ctx" in error:
                    detail["ctx"] = error["ctx"]
                errors.append(detail)
    for name in raw:
        if name not in model.model_fields:
            errors.append({"type": "extra_forbidden", "loc": (name,), "input": raw[name]})
    if errors:
        raise ValidationError.from_exception_data(model.__name__, errors)
    if isinstance(value, model):
        validate_immutable(value)
    result = model.model_validate(checked, strict=True)
    validate_immutable(result)
    return result
