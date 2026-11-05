"""Settings values and content identity; these are not publication-pinned captures."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.identity.uid import EntityUid
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class WorldPhysicsSettingsRef(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    world_uid: EntityUid
    schema_version: StrictInt = Field(ge=1)
    content_revision: RevisionHex


class WorldPhysicsSettingsView(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    settings: WorldPhysicsSettings
    ref: WorldPhysicsSettingsRef
