"""Immutable, serializable field path of a validated value.

Plan: ``.cursor/plans/error-contracts-1.md`` §3.9 C0-3. Built by
``CheckedPath.freeze``; ``projection`` is the only flat form, for HTTP/log.
"""

from inspect import isabstract
from typing import Annotated, Literal, Self, TypeGuard

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

_RECORD = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")


class ModelIdentityError(ValueError):
    """The supplied owner cannot be represented by a stable model identity."""


def is_model_identity_owner(model: object) -> TypeGuard[type[BaseModel]]:
    if not isinstance(model, type) or not issubclass(model, BaseModel) or model is BaseModel or isabstract(model):
        return False
    metadata = model.__pydantic_generic_metadata__
    return metadata["origin"] is None and not metadata["parameters"]


class ModelIdentity(BaseModel):
    """Model class identity; cold restore resolves it only via a manifest allowlist."""

    model_config = _RECORD

    module: StrictStr
    qualname: StrictStr

    @classmethod
    def of(cls, model: object) -> Self:
        if not is_model_identity_owner(model):
            raise ModelIdentityError("model identity requires a named concrete BaseModel class")
        return cls(module=model.__module__, qualname=model.__qualname__)


class FieldSegment(BaseModel):
    model_config = _RECORD

    kind: Literal["field"] = "field"
    owner: ModelIdentity
    name: StrictStr


class IndexSegment(BaseModel):
    model_config = _RECORD

    kind: Literal["index"] = "index"
    index: Annotated[StrictInt, Field(ge=0)]


class KeySegment(BaseModel):
    model_config = _RECORD

    kind: Literal["key"] = "key"
    key: StrictStr | StrictInt


class VariantSegment(BaseModel):
    """Selected union branch; adds no element to ``projection``."""

    model_config = _RECORD

    kind: Literal["variant"] = "variant"
    branch: ModelIdentity


type PathSegment = Annotated[
    FieldSegment | IndexSegment | KeySegment | VariantSegment, Field(discriminator="kind")
]


class ValidatedFieldPath(BaseModel):
    model_config = _RECORD

    root: ModelIdentity
    segments: Annotated[tuple[PathSegment, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _starts_at_root_field(self) -> Self:
        first = self.segments[0]
        if not isinstance(first, FieldSegment) or first.owner != self.root:
            raise ValueError("path must start with a field of its root model")
        return self

    def projection(self) -> tuple[str | int, ...]:
        flat: list[str | int] = []
        for segment in self.segments:
            if isinstance(segment, FieldSegment):
                flat.append(segment.name)
            elif isinstance(segment, IndexSegment):
                flat.append(segment.index)
            elif isinstance(segment, KeySegment):
                flat.append(segment.key)
        return tuple(flat)
