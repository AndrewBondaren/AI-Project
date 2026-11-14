"""Immutable descriptor configuration; owning key adapters remain in application."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import GetCoreSchemaHandler, model_validator
from pydantic_core import core_schema

from app.dataModel.registryKey import RegistryKey
from app.dataModel.sourceVersioning._value import SourceValue


class SourceDescriptorCategory(StrEnum):
    REGISTRY_MEMBER = "registry_member"
    LIBRARY_MEMBER = "library_member"
    ENTITY = "entity"
    SETTINGS = "settings"
    COLLECTION = "collection"


class SourceDescriptorScope(StrEnum):
    WORLD = "world"
    GLOBAL = "global"


class SourceMemberKeyKind(StrEnum):
    NONE = "none"
    TEXT = "text"
    UUID = "uuid"


class SourceCollectionOrder(StrEnum):
    SET = "set"
    SEQUENCE = "sequence"


class SourceMemberKey(str):
    """Exact wire token, not an owning registry membership certificate."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls, core_schema.str_schema(strict=True, min_length=1),
            serialization=core_schema.to_string_ser_schema(when_used="json"),
        )


class SourceDescriptorRegistry(SourceValue, frozen=True):
    entries: tuple[SourceDescriptorDefinition, ...]

    @model_validator(mode="after")
    def valid_roster(self) -> Self:
        entries = {entry.key: entry for entry in self.entries}
        if len(entries) != len(self.entries):
            raise ValueError("duplicate descriptor key")
        for entry in self.entries:
            for member in entry.member_descriptors:
                definition = entries.get(member)
                if definition is None or definition.category is SourceDescriptorCategory.COLLECTION:
                    raise ValueError("collection member must name a registered non-collection descriptor")
        return self


type SourceDescriptorKey = RegistryKey[SourceDescriptorRegistry]


class SourceDescriptorDefinition(SourceValue, frozen=True):
    key: SourceDescriptorKey
    category: SourceDescriptorCategory
    scope: SourceDescriptorScope
    key_kind: SourceMemberKeyKind
    collection_order: SourceCollectionOrder | None
    member_descriptors: tuple[SourceDescriptorKey, ...]

    @model_validator(mode="after")
    def valid_shape(self) -> Self:
        if not self.key or any(not member for member in self.member_descriptors):
            raise ValueError("descriptor keys must be nonempty")
        category = self.category
        expected_scope = (
            SourceDescriptorScope.GLOBAL
            if category is SourceDescriptorCategory.LIBRARY_MEMBER
            else SourceDescriptorScope.WORLD
        )
        if self.scope is not expected_scope:
            raise ValueError("descriptor scope does not match category")
        if category is SourceDescriptorCategory.REGISTRY_MEMBER:
            if self.key_kind not in (SourceMemberKeyKind.TEXT, SourceMemberKeyKind.UUID):
                raise ValueError("registry member requires TEXT or UUID")
        elif category is SourceDescriptorCategory.LIBRARY_MEMBER:
            if self.key_kind is not SourceMemberKeyKind.UUID:
                raise ValueError("library member requires UUID")
        elif self.key_kind is not SourceMemberKeyKind.NONE:
            raise ValueError("entity, settings and collection require NONE")
        if category is SourceDescriptorCategory.COLLECTION:
            if self.collection_order is None or not self.member_descriptors:
                raise ValueError("collection requires order and member descriptors")
            if len(set(self.member_descriptors)) != len(self.member_descriptors):
                raise ValueError("duplicate member descriptor")
        elif self.collection_order is not None or self.member_descriptors:
            raise ValueError("non-collection cannot declare membership configuration")
        return self


SourceDescriptorRegistry.model_rebuild()
