"""Closed settings preparation refusal reasons."""

from enum import StrEnum

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsRef


class PhysicsSettingsChangeReason(StrEnum):
    REVISION_MISMATCH = "revision_mismatch"


class PhysicsSettingsChangeRefused(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    reason: PhysicsSettingsChangeReason
    expected_ref: WorldPhysicsSettingsRef
    observed_ref: WorldPhysicsSettingsRef

    @model_validator(mode="after")
    def different_revisions(self) -> Self:
        if (self.expected_ref.world_uid != self.observed_ref.world_uid
                or self.expected_ref.schema_version != self.observed_ref.schema_version
                or self.expected_ref.content_revision == self.observed_ref.content_revision):
            raise ValueError("revision mismatch requires same world/schema and different revisions")
        return self
