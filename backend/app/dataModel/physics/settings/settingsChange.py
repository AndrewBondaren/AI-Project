"""Pure preparation data, not durable publication receipts."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsRef, WorldPhysicsSettingsView
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings


class WorldPhysicsSettingsReplace(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    world_uid: EntityUid
    expected_ref: WorldPhysicsSettingsRef
    value: WorldPhysicsSettings

    @model_validator(mode="after")
    def matching_world(self) -> Self:
        if self.world_uid != self.expected_ref.world_uid:
            raise ValueError("settings expectation belongs to another world")
        return self


class WorldPhysicsSettingsReset(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    world_uid: EntityUid
    expected_ref: WorldPhysicsSettingsRef

    @model_validator(mode="after")
    def matching_world(self) -> Self:
        if self.world_uid != self.expected_ref.world_uid:
            raise ValueError("settings expectation belongs to another world")
        return self


class PreparedPhysicsSettingsChange(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    world_uid: EntityUid
    expected_ref: WorldPhysicsSettingsRef
    proposed: WorldPhysicsSettings
    proposed_ref: WorldPhysicsSettingsRef

    @model_validator(mode="after")
    def matching_refs(self) -> Self:
        if not self.world_uid == self.expected_ref.world_uid == self.proposed_ref.world_uid:
            raise ValueError("settings change contains another world")
        if self.expected_ref.schema_version != self.proposed_ref.schema_version:
            raise ValueError("settings preparation cannot migrate schema versions")
        WorldPhysicsSettingsView(settings=self.proposed, ref=self.proposed_ref)
        return self
