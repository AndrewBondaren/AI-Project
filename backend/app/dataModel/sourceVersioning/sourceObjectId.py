"""Source identities; descriptor registration and owning key validation are external."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceDescriptor import (
    SourceDescriptorCategory, SourceDescriptorKey, SourceMemberKey,
)


class _SourceIdentity(SourceValue, frozen=True):
    @model_validator(mode="before")
    @classmethod
    def exact_kind(cls, value: object, info: ValidationInfo) -> object:
        if (info.mode == "python" and isinstance(value, dict) and "kind" in value
                and type(value["kind"]) is not SourceDescriptorCategory):
            raise ValueError("kind requires SourceDescriptorCategory in Python")
        return value

    @field_validator("descriptor", check_fields=False)
    @classmethod
    def nonempty_descriptor(cls, value: SourceDescriptorKey) -> SourceDescriptorKey:
        if not value:
            raise ValueError("empty descriptor key")
        return value


class RegistryMemberId(_SourceIdentity, frozen=True):
    kind: Literal[SourceDescriptorCategory.REGISTRY_MEMBER]
    world_uid: EntityUid
    descriptor: SourceDescriptorKey
    member_key: SourceMemberKey


class LibraryMemberId(_SourceIdentity, frozen=True):
    kind: Literal[SourceDescriptorCategory.LIBRARY_MEMBER]
    descriptor: SourceDescriptorKey
    template_uid: EntityUid

    @field_validator("template_uid")
    @classmethod
    def canonical_uuid(cls, value: str) -> str:
        if str(UUID(value)) != value:
            raise ValueError("template_uid must be a canonical lowercase hyphenated UUID")
        return value


class EntityObjectId(_SourceIdentity, frozen=True):
    kind: Literal[SourceDescriptorCategory.ENTITY]
    world_uid: EntityUid
    descriptor: SourceDescriptorKey
    entity_uid: EntityUid


class SourceSettingsId(_SourceIdentity, frozen=True):
    kind: Literal[SourceDescriptorCategory.SETTINGS]
    world_uid: EntityUid
    descriptor: SourceDescriptorKey


class SourceCollectionId(_SourceIdentity, frozen=True):
    kind: Literal[SourceDescriptorCategory.COLLECTION]
    world_uid: EntityUid
    descriptor: SourceDescriptorKey


type SourceObjectId = Annotated[
    RegistryMemberId | LibraryMemberId | EntityObjectId | SourceSettingsId,
    Field(discriminator="kind"),
]
