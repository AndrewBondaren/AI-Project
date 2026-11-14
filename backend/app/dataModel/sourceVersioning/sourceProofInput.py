"""Declared usage preserves order and repetitions for the owning normalizer."""

# TODO(SOURCE-TYPED-ERRORS): Migrate the manual ValueError diagnostics below to
# the agreed Source typed-error contract; independent failures need aggregation.
# This transition and its acceptance criterion remain OPEN.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

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
