"""Dependency ordinals; fingerprint matching and proof bounds are application checks."""

# TODO(SOURCE-TYPED-ERRORS): Migrate the manual ValueError diagnostics below to
# the agreed Source typed-error contract; independent failures need aggregation.
# This transition and its acceptance criterion remain OPEN.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

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
