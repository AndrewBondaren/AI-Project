"""Result value; construction neither computes closure nor acquires holds."""

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
