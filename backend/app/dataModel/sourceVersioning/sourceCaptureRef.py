"""Witness reference shape. Construction does not prove committed finalization."""

# TODO(SOURCE-TYPED-ERRORS): Migrate the manual ValueError diagnostics below to
# the agreed Source typed-error contract; independent failures need aggregation.
# This transition and its acceptance criterion remain OPEN.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

from typing import Self

from pydantic import model_validator

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning._value import SourceValue


class SourceCaptureRef(SourceValue, frozen=True):
    world_uid: EntityUid
    artifact: ArtifactRef

    @model_validator(mode="after")
    def witness_shape(self) -> Self:
        ref = self.artifact
        if (
            ref.kind is not ArtifactKind.SQL_ROWS
            or ref.format_key != "source.capture-witness"
            or ref.format_version != 1
            or ref.row_count != 1
        ):
            raise ValueError("capture requires source.capture-witness v1 SQL_ROWS with row_count=1")
        return self
