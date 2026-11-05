"""Settings values and content identity; these are not publication-pinned captures."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, TypeAdapter, model_validator

from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.identity.uid import EntityUid
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.validation.immutableValue import validate_immutable
from app.encoding.canonicalCodec import content_digest, encode

_PRIMITIVE_MANIFEST = CanonicalSchemaManifest(entries=())


class WorldPhysicsSettingsRef(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    world_uid: EntityUid
    schema_version: StrictInt = Field(ge=1)
    content_revision: RevisionHex


def settings_ref(world_uid: EntityUid, settings: WorldPhysicsSettings) -> WorldPhysicsSettingsRef:
    """Version-one world-bound identity; shared by construction and revalidation."""
    validate_immutable(settings)
    settings = WorldPhysicsSettings.model_validate(settings, strict=True)
    world_uid = TypeAdapter(EntityUid).validate_python(world_uid, strict=True)
    projection = (settings.SCHEMA_ID, settings.SCHEMA_VERSION, world_uid,
                  tuple((name, getattr(settings, name)) for name in WorldPhysicsSettings.model_fields))
    return WorldPhysicsSettingsRef(world_uid=world_uid, schema_version=settings.SCHEMA_VERSION,
        content_revision=content_digest(encode(projection, _PRIMITIVE_MANIFEST)).hex())


class WorldPhysicsSettingsView(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    settings: WorldPhysicsSettings
    ref: WorldPhysicsSettingsRef

    @model_validator(mode="after")
    def matching_content(self) -> Self:
        if self.ref != settings_ref(self.ref.world_uid, self.settings):
            raise ValueError("settings view content or schema version does not match its ref")
        return self
