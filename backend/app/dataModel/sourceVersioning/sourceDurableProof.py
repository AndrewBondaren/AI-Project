"""Persisted proof shape; canonical ordering and authority require Source admission."""

from typing import Literal, Self

from pydantic import field_validator, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning._value import SourceValue
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
        captures = set()
        for use in self.uses:
            if use.capture.world_uid != self.world_uid:
                raise ValueError("capture world differs from proof world")
            if use.capture in captures:
                raise ValueError("persisted proof contains duplicate capture")
            captures.add(use.capture)
            deps = use.dependencies
            if not deps.objects and not deps.collections:
                raise ValueError("persisted proof cannot contain empty usage")
            if len({ref.object_id for ref in deps.objects}) != len(deps.objects):
                raise ValueError("persisted usage requires one revision per object identity")
            if len({ref.collection_id for ref in deps.collections}) != len(deps.collections):
                raise ValueError("persisted usage requires one revision per collection identity")
        return self
