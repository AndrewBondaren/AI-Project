"""Typed authoring result and producer-authorized gravity fallback fact."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.dataModel.physics.settings.settingsIssues import PhysicsGravityTypeError, restore_json_issue_records
from app.dataModel.physics.settings.worldPhysicsSettings import (
    NonnegativeFinite, STANDARD_GRAVITY_M_S2, WorldPhysicsSettings,
)
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue

_RECORD = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")


class PhysicsGravityDefaultApplied(BaseModel):
    model_config = _RECORD
    cause: PhysicsGravityTypeError
    selected: NonnegativeFinite

    @model_validator(mode="after")
    def declared_default(self) -> Self:
        if self.selected != STANDARD_GRAVITY_M_S2:
            raise ValueError("fallback must select the declared gravity default")
        return self


class PhysicsSettingsInputResolved(BaseModel):
    model_config = _RECORD
    settings: WorldPhysicsSettings
    diagnostics: Annotated[tuple[PhysicsGravityDefaultApplied, ...], Field(max_length=1)] = ()

    @model_validator(mode="after")
    def matching_fallback(self) -> Self:
        if self.diagnostics and self.settings.gravity_acceleration_m_s2 != self.diagnostics[0].selected:
            raise ValueError("resolved settings must contain the selected default")
        return self


class PhysicsSettingsInputRefused(BaseModel):
    model_config = _RECORD
    issues: Annotated[
        tuple[PhysicsGravityTypeError | JsonFieldError | WireShapeIssue, ...], Field(min_length=1),
    ]

    @field_validator("issues", mode="before")
    @classmethod
    def restore_json_issues(cls, value: object, info: ValidationInfo) -> object:
        return restore_json_issue_records(value, info)
