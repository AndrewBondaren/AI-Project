"""Public input for activating a prepared Pack against a pinned world publication."""
from typing import Self

from app.dataModel.worldPack.activation.candidate import PreparedPackCandidate
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class PackActivationInput(PreparedPackCandidate):
    expected: WorldPublicationRef

    @classmethod
    def from_candidate(cls, candidate: PreparedPackCandidate, expected: WorldPublicationRef) -> Self:
        return cls(operation_id=candidate.operation_id, manifest=candidate.manifest,
                   preparation_fingerprint=candidate.preparation_fingerprint, expected=expected)
