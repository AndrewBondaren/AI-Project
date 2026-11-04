"""Runtime binding of a ``FieldRef`` to one direct POJO field.

Plan: ``.cursor/plans/error-contracts-1.md`` §0.1.1.
"""

from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel

from app.dataModel.fields.fieldRef import FieldRef


@dataclass(frozen=True)
class BoundField:
    """Introspected field identity, independent of selector identity."""

    model: type[BaseModel]
    field: str


class _SelectedField:
    def __bool__(self):
        raise ValueError("field selector must select one direct attribute")


class _FieldProbe:
    def __init__(self, selections):
        object.__setattr__(self, "_selections", selections)

    def __getattribute__(self, name):
        selected = _SelectedField()
        object.__getattribute__(self, "_selections").append((name, selected))
        return selected


def bind_field(ref: FieldRef[Any, Any], *, computed: bool = False) -> BoundField:
    """Resolve a direct selector; no source object/default is evaluated."""
    if not isinstance(ref, FieldRef):
        raise ValueError("field reference must be FieldRef")
    try:
        model = ref.model()
    except Exception as exc:
        raise ValueError("cannot resolve FieldRef model supplier") from exc
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise ValueError("field reference must refer to a POJO model")
    selections = []
    try:
        result = ref.select(cast(Any, _FieldProbe(selections)))
    except Exception as exc:
        raise ValueError("field selector must select one direct attribute") from exc
    if len(selections) != 1 or result is not selections[0][1]:
        raise ValueError("field selector must select one direct attribute")
    name = selections[0][0]
    if name not in model.model_fields and not (
        computed and name in model.model_computed_fields
    ):
        raise ValueError(f"{model.__name__}: no such field '{name}'")
    return BoundField(model, name)
