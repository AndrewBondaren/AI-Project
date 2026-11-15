"""Dependency ordinals; fingerprint matching and proof bounds are application checks."""

# TODO(SOURCE-TYPED-ERRORS): Migrate the manual ValueError diagnostics below to
# the agreed Source typed-error contract; independent failures need aggregation.
# This transition and its acceptance criterion remain OPEN.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

from typing import Annotated, Self

from pydantic import Field, StrictInt, field_validator, model_validator

from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning._proofValueRules import invalid_selection_order_positions
from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class SourceProofSelection(SourceValue, frozen=True):
    proof_fingerprint: RevisionHex
    dependency_indices: tuple[Annotated[StrictInt, Field(ge=0)], ...]

    @field_validator("dependency_indices")
    @classmethod
    def increasing_indices(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if invalid_selection_order_positions(value):
            raise ValueError("dependency indices must be strictly increasing and unique")
        return value


class SourceProofSelectInput(SourceValue, frozen=True):
    world_uid: EntityUid
    proof: SourceDurableProof
    selection: SourceProofSelection

    @model_validator(mode="after")
    def proof_world(self) -> Self:
        if self.proof.world_uid != self.world_uid:
            raise ValueError("proof world differs from request world")
        return self
