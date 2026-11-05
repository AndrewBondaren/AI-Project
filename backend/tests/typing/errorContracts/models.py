"""Fixture POJOs shared by the error-contract typing fixtures."""

from collections.abc import Mapping, Sequence
from enum import StrEnum

from pydantic import BaseModel

from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class Meta(BaseModel):
    source_uid: str


class Item(BaseModel):
    source_uid: str


class Inp(BaseModel):
    name: str
    metadata: Meta | None = None
    items: tuple[Item, ...] = ()
    values: list[int] = []
    weights: Sequence[float] = ()
    tags: dict[str, int] = {}
    blobs: Mapping[str, bytes] = {}


class Other(BaseModel):
    number: int


class FixtureCode(StrEnum):
    MISSING = "missing"


class OtherCode(StrEnum):
    BROKEN = "broken"


class FixtureTypeError(FieldPathError[FixtureCode]):
    pass


INP_NAME = FieldRef(lambda: Inp, lambda pojo: pojo.name)
INP_METADATA = FieldRef(lambda: Inp, lambda pojo: pojo.metadata)
INP_ITEMS = FieldRef(lambda: Inp, lambda pojo: pojo.items)
INP_VALUES = FieldRef(lambda: Inp, lambda pojo: pojo.values)
INP_WEIGHTS = FieldRef(lambda: Inp, lambda pojo: pojo.weights)
INP_TAGS = FieldRef(lambda: Inp, lambda pojo: pojo.tags)
INP_BLOBS = FieldRef(lambda: Inp, lambda pojo: pojo.blobs)
META_SOURCE = FieldRef(lambda: Meta, lambda pojo: pojo.source_uid)
ITEM_SOURCE = FieldRef(lambda: Item, lambda pojo: pojo.source_uid)
OTHER_NUMBER = FieldRef(lambda: Other, lambda pojo: pojo.number)
