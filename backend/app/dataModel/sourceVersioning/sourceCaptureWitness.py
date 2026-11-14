"""Immutable finalize candidate; construction is not committed Source evidence."""

# TODO(SOURCE-TYPED-ERRORS): Semantic diagnostics at the Source boundary remain
# OPEN; see .cursor/plans/source-g1-values-canonical-implementation.md §3.

from typing import Self

from pydantic import model_validator

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning._value import SourceValue


class SourceCaptureWitness(SourceValue, frozen=True):
    capture_uid: EntityUid
    world_uid: EntityUid
    capture_body: ArtifactRef

    @model_validator(mode="after")
    def capture_body_shape(self) -> Self:
        ref = self.capture_body
        if ref.kind is not ArtifactKind.BLOB or ref.format_key != "source.capture" or ref.format_version != 1:
            raise ValueError("witness requires source.capture v1 BLOB")
        return self
