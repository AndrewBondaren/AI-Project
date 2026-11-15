"""Persisted proof shape; canonical ordering and authority require Source admission."""

# TODO(SOURCE-TYPED-ERRORS): Migrate the manual ValueError diagnostics below to
# the agreed Source typed-error contract; independent failures need aggregation.
# This transition and its acceptance criterion remain OPEN.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

from typing import Literal, Self

from pydantic import field_validator, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning._proofValueRules import (
    duplicate_capture_positions, has_dependencies,
    has_unique_collection_identities, has_unique_object_identities,
)
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage


class SourceDurableProof(SourceValue, frozen=True):
    schema_version: Literal[1]
    world_uid: EntityUid
    uses: tuple[SourceCaptureUsage, ...]

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version_type(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an exact integer")
        return value

    @model_validator(mode="after")
    def persisted_shape(self) -> Self:
        duplicates = set(duplicate_capture_positions(self.uses))
        for index, use in enumerate(self.uses):
            if use.capture.world_uid != self.world_uid:
                raise ValueError("capture world differs from proof world")
            if index in duplicates:
                raise ValueError("persisted proof contains duplicate capture")
            deps = use.dependencies
            if not has_dependencies(deps):
                raise ValueError("persisted proof cannot contain empty usage")
            if not has_unique_object_identities(deps.objects):
                raise ValueError("persisted usage requires one revision per object identity")
            if not has_unique_collection_identities(deps.collections):
                raise ValueError("persisted usage requires one revision per collection identity")
        return self
