"""Result value; construction neither computes closure nor acquires holds."""

# TODO(SOURCE-TYPED-ERRORS): Migrate the manual ValueError diagnostics below to
# the agreed Source typed-error contract; independent failures need aggregation.
# This transition and its acceptance criterion remain OPEN.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

from typing import Self

from pydantic import model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof


class SourceProofResult(SourceValue, frozen=True):
    proof: SourceDurableProof
    durable_refs: tuple[ArtifactRef, ...]

    @model_validator(mode="after")
    def refs_shape(self) -> Self:
        if len(set(self.durable_refs)) != len(self.durable_refs):
            raise ValueError("duplicate durable ref")
        if not self.proof.uses and self.durable_refs:
            raise ValueError("empty proof requires empty source closure")
        if self.proof.uses and not self.durable_refs:
            raise ValueError("nonempty proof requires durable refs")
        return self
