"""Cache namespace metadata; payload binding and codecs belong to application."""

from __future__ import annotations

from typing import Generic, NewType, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.registryKey import RegistryKey


CacheSchemaVersion = NewType("CacheSchemaVersion", int)
T = TypeVar("T")


class CacheContractRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    entries: tuple[CacheContractMetadata, ...]

    @model_validator(mode="after")
    def unique_ids(self) -> CacheContractRegistry:
        if len({entry.id for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate cache contract id")
        return self


type CacheContractId = RegistryKey[CacheContractRegistry]


class CacheContractMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    id: CacheContractId
    schema_version: CacheSchemaVersion = Field(strict=True, gt=0)


class CacheContract(CacheContractMetadata, Generic[T]):
    """Invariant T preserves the application's registered payload binding."""


CacheContractRegistry.model_rebuild()
