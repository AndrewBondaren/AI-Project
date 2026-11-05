"""Physics settings causes; policy belongs to the application operation."""

import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, TypeAdapter, ValidationInfo, field_validator, model_validator

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath
from app.dataModel.identity.uid import EntityUid
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsRef
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.wireLocation import WireLocation, WirePart
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue

_RECORD = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
GRAVITY = FieldRef(lambda: WorldPhysicsSettings, lambda settings: settings.gravity_acceleration_m_s2)
GRAVITY_PATH = CheckedPath.root(WorldPhysicsSettings).field(GRAVITY).freeze()


def restore_json_issue_records(value: object, info: ValidationInfo) -> object:
    """Restore declared JSON containers before the shared strict wrap handler.

    Every restored value uses its existing schema; the original issue schema
    still validates code, arguments, extras and all model invariants afterwards.
    This is JSON boundary handling, not coercion of Python input or a codec.
    """
    if info.mode != "json" or not isinstance(value, list):
        return value
    restored: list[object] = []
    for issue in value:
        if isinstance(issue, dict):
            issue = dict(issue)
            if "path" in issue:
                issue["path"] = ValidatedFieldPath.model_validate_json(json.dumps(issue["path"]))
            if "location" in issue:
                issue["location"] = WireLocation.model_validate_json(json.dumps(issue["location"]))
            if "wire_path" in issue:
                issue["wire_path"] = TypeAdapter(tuple[WirePart, ...]).validate_json(json.dumps(issue["wire_path"]))
        restored.append(issue)
    return tuple(restored)


class PhysicsGravityCode(StrEnum):
    INVALID_GRAVITY = "invalid_gravity"


class PhysicsGravityArguments(BaseModel):
    model_config = _RECORD
    pydantic_type: Literal["float_type", "greater_than_equal", "finite_number"]


class PhysicsGravityTypeError(FieldPathError[PhysicsGravityCode]):
    code: PhysicsGravityCode
    arguments: PhysicsGravityArguments
    location: WireLocation

    @field_validator("path", "location", mode="before")
    @classmethod
    def restore_json_records(cls, value: object, info: ValidationInfo) -> object:
        # Pydantic 2.13's wrap handler treats nested strict tuples as Python
        # input. Restore these declared records through their own JSON schemas;
        # Python input remains strict and the shared carrier is unchanged.
        if info.mode == "json" and isinstance(value, dict):
            wire = json.dumps(value)
            if info.field_name == "path":
                return ValidatedFieldPath.model_validate_json(wire)
            return WireLocation.model_validate_json(wire)
        return value

    @model_validator(mode="after")
    def gravity_field(self) -> Self:
        if self.path != GRAVITY_PATH:
            raise ValueError("gravity issue requires the WorldPhysicsSettings gravity field")
        return self


class PhysicsSettingsSubject(StrEnum):
    SETTINGS = "settings"
    VIEW = "view"
    REPLACE = "replace"
    RESET = "reset"
    PREPARED = "prepared"
    INPUT = "input"


class PhysicsSettingsInputOperation(StrEnum):
    VALIDATE = "validate"
    RUNTIME = "runtime"


class PhysicsSettingsContextMode(StrEnum):
    IMPORT = "import"
    RUNTIME = "runtime"


class PhysicsSettingsAdmissionKind(StrEnum):
    WORLD_MISMATCH = "world_mismatch"
    SCHEMA_MISMATCH = "schema_mismatch"
    CONTENT_MISMATCH = "content_mismatch"
    MALFORMED_CONTRACT = "malformed_contract"
    POLICY_MISMATCH = "policy_mismatch"


class SettingsWorldMismatch(BaseModel):
    model_config = _RECORD
    kind: Literal[PhysicsSettingsAdmissionKind.WORLD_MISMATCH] = PhysicsSettingsAdmissionKind.WORLD_MISMATCH
    expected_world_uid: EntityUid
    observed_world_uid: EntityUid

    @model_validator(mode="after")
    def different_worlds(self) -> Self:
        if self.expected_world_uid == self.observed_world_uid:
            raise ValueError("world mismatch requires different worlds")
        return self


class SettingsSchemaMismatch(BaseModel):
    model_config = _RECORD
    kind: Literal[PhysicsSettingsAdmissionKind.SCHEMA_MISMATCH] = PhysicsSettingsAdmissionKind.SCHEMA_MISMATCH
    expected_version: StrictInt = Field(ge=1)
    observed_version: StrictInt = Field(ge=1)

    @model_validator(mode="after")
    def different_versions(self) -> Self:
        if self.expected_version == self.observed_version:
            raise ValueError("schema mismatch requires different versions")
        return self


class SettingsContentMismatch(BaseModel):
    model_config = _RECORD
    kind: Literal[PhysicsSettingsAdmissionKind.CONTENT_MISMATCH] = PhysicsSettingsAdmissionKind.CONTENT_MISMATCH
    declared: WorldPhysicsSettingsRef
    computed: WorldPhysicsSettingsRef

    @model_validator(mode="after")
    def different_content(self) -> Self:
        if (self.declared.world_uid != self.computed.world_uid
                or self.declared.schema_version != self.computed.schema_version
                or self.declared.content_revision == self.computed.content_revision):
            raise ValueError("content mismatch requires same world/schema and different content")
        return self


class SettingsMalformedContract(BaseModel):
    model_config = _RECORD
    kind: Literal[PhysicsSettingsAdmissionKind.MALFORMED_CONTRACT] = PhysicsSettingsAdmissionKind.MALFORMED_CONTRACT
    subject: PhysicsSettingsSubject
    issues: Annotated[tuple[JsonFieldError | WireShapeIssue, ...], Field(min_length=1)]

    @field_validator("issues", mode="before")
    @classmethod
    def restore_json_issues(cls, value: object, info: ValidationInfo) -> object:
        return restore_json_issue_records(value, info)


class SettingsPolicyMismatch(BaseModel):
    model_config = _RECORD
    kind: Literal[PhysicsSettingsAdmissionKind.POLICY_MISMATCH] = PhysicsSettingsAdmissionKind.POLICY_MISMATCH
    operation: PhysicsSettingsInputOperation
    actual_mode: PhysicsSettingsContextMode
    actual_validate_only: StrictBool

    @model_validator(mode="after")
    def different_policy(self) -> Self:
        valid = (self.actual_validate_only if self.operation is PhysicsSettingsInputOperation.VALIDATE
                 else self.actual_mode is PhysicsSettingsContextMode.RUNTIME and not self.actual_validate_only)
        if valid:
            raise ValueError("policy mismatch requires an incompatible context")
        return self


class PhysicsSettingsAdmissionFailure(BaseModel):
    model_config = _RECORD
    cause: Annotated[
        SettingsWorldMismatch | SettingsSchemaMismatch | SettingsContentMismatch
        | SettingsMalformedContract | SettingsPolicyMismatch,
        Field(discriminator="kind"),
    ]
