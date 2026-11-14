"""Declared usage preserves order and repetitions for the owning normalizer."""

from typing import Self

from pydantic import model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage


class SourceProofInput(SourceValue, frozen=True):
    world_uid: EntityUid
    uses: tuple[SourceCaptureUsage, ...]

    @model_validator(mode="after")
    def capture_worlds(self) -> Self:
        if any(use.capture.world_uid != self.world_uid for use in self.uses):
            raise ValueError("capture world differs from input world")
        return self
