"""Closed settings preparation refusal reasons."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class PhysicsSettingsChangeReason(StrEnum):
    INVALID_SETTINGS = "invalid_settings"
    STALE_SETTINGS = "stale_settings"
    WORLD_MISSING = "world_missing"
    UNSUPPORTED_LIFECYCLE = "unsupported_lifecycle"


class PhysicsSettingsChangeRefused(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    reason: PhysicsSettingsChangeReason
