"""Immutable content identity, not a path or a concrete storage backend.

tz_world_snapshot, ArtifactRef/staging contract; registry membership is an
application boundary. A row-set representation survives backend replacement.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.patch.values import FormatVersion
from app.dataModel.registryKey import RegistryKey
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class ArtifactKind(StrEnum):
    BLOB = "blob"
    SQL_ROWS = "sql_rows"


class ArtifactFormatRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    entries: tuple[ArtifactFormatMetadata, ...]

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        if len({entry.key for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate artifact format key")
        return self


type ArtifactFormatKey = RegistryKey[ArtifactFormatRegistry]


class ArtifactFormatMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    key: ArtifactFormatKey
    supported_versions: frozenset[FormatVersion] = Field(min_length=1)


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: ArtifactKind
    format_key: ArtifactFormatKey
    format_version: FormatVersion
    content_hash: RevisionHex
    nbytes: Annotated[StrictInt, Field(ge=0)]
    row_count: Annotated[StrictInt, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def representation_fields(self) -> Self:
        if self.kind is ArtifactKind.SQL_ROWS and self.row_count is None:
            raise ValueError("SQL_ROWS requires row_count")
        if self.kind is ArtifactKind.BLOB and self.row_count is not None:
            raise ValueError("BLOB cannot declare row_count")
        return self


ArtifactFormatRegistry.model_rebuild()
