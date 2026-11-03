"""Structural bounds for a canonical decode operation."""
from dataclasses import dataclass
from typing import get_origin

from pydantic import BaseModel

from app.dataModel.cascade.cascadeGraph import BoundField, bind_field
from app.dataModel.cascade.cascadeSpec import FieldRef


@dataclass(frozen=True, init=False)
class CollectionLimit[M: BaseModel, C: (tuple[object, ...] | frozenset[object])]:
    ref: FieldRef[M, C]
    maximum: int
    minimum: int
    bound: BoundField

    def __init__(self, expected: type[C], /, *, ref: FieldRef[M, C], maximum: int, minimum: int = 0) -> None:
        field = bind_field(ref)
        annotation = field.model.model_fields[field.field].annotation
        if get_origin(annotation) not in (tuple, frozenset):
            raise ValueError(f"expected canonical collection: {field.model.__name__}.{field.field}")
        if annotation != expected:
            raise ValueError(f"collection type mismatch: {field.model.__name__}.{field.field}")
        object.__setattr__(self, "ref", ref)
        object.__setattr__(self, "bound", field)
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)

    def admits(self, size: int) -> bool:
        return self.minimum <= size <= self.maximum


@dataclass(frozen=True)
class RecordLimits:
    owner: type[BaseModel]
    collections: tuple[CollectionLimit, ...]

    def __post_init__(self) -> None:
        for rule in self.collections:
            if rule.bound.model is not self.owner:
                raise ValueError(f"bounded field belongs to {rule.bound.model.__name__}, expected {self.owner.__name__}")


@dataclass(frozen=True)
class DecodeLimits:
    max_bytes: int
    max_nodes: int
    max_depth: int
    max_items: int
    field_sizes: tuple[RecordLimits, ...] = ()
