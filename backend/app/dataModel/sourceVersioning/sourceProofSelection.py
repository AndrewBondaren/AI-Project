"""Dependency ordinals; fingerprint matching and proof bounds are application checks."""

from typing import Annotated

from pydantic import Field, StrictInt, field_validator

from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class SourceProofSelection(SourceValue, frozen=True):
    proof_fingerprint: RevisionHex
    dependency_indices: tuple[Annotated[StrictInt, Field(ge=0)], ...]

    @field_validator("dependency_indices")
    @classmethod
    def increasing_indices(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(left >= right for left, right in zip(value, value[1:])):
            raise ValueError("dependency indices must be strictly increasing and unique")
        return value
