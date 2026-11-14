"""Witness reference shape. Construction does not prove committed finalization."""

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
