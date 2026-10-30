"""Section declarations only; application owns codecs, membership and dispatch."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.patch.values import FormatVersion
from app.dataModel.registryKey import RegistryKey


class PatchSectionRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    entries: tuple[PatchSectionMetadata, ...]

    @model_validator(mode="after")
    def unique_keys(self) -> Self:
        if len({entry.key for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate patch section key")
        return self


type SectionKey = RegistryKey[PatchSectionRegistry]


class PatchSectionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    key: SectionKey
    supported_versions: frozenset[FormatVersion] = Field(min_length=1)


PatchSectionRegistry.model_rebuild()
