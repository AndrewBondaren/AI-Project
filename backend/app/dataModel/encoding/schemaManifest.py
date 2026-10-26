"""Explicit type identities for canonical serialization; no executable codecs."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class CanonicalTypeKind(StrEnum):
    RECORD = "record"
    ENUM = "enum"


class RegisteredTypeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    type_id: StrictInt = Field(gt=0)
    python_type: type
    kind: CanonicalTypeKind


class CanonicalSchemaManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    entries: tuple[RegisteredTypeEntry, ...]

    @model_validator(mode="after")
    def unique_types(self) -> Self:
        if len({entry.type_id for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate canonical type id")
        if len({entry.python_type for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate canonical owner type")
        return self
