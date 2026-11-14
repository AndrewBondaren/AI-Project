"""Declared dependencies of one capture; no full-read-set certificate."""

# TODO(SOURCE-TYPED-ERRORS): Migrate the manual ValueError diagnostics below to
# the agreed Source typed-error contract; independent failures need aggregation.
# This transition and its acceptance criterion remain OPEN.
# Plan: [G1 §3](../../../../.cursor/plans/source-g1-values-canonical-implementation.md#3-g11--значения-и-structural-validation).

from typing import Self

from pydantic import model_validator

from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceCaptureRef import SourceCaptureRef
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceObjectId import LibraryMemberId


class SourceCaptureUsage(SourceValue, frozen=True):
    capture: SourceCaptureRef
    dependencies: SourceDependencySet

    @model_validator(mode="after")
    def dependency_worlds(self) -> Self:
        world = self.capture.world_uid
        for ref in self.dependencies.objects:
            identity = ref.object_id
            if not isinstance(identity, LibraryMemberId) and identity.world_uid != world:
                raise ValueError("object world differs from capture world")
        for ref in self.dependencies.collections:
            if ref.collection_id.world_uid != world:
                raise ValueError("collection world differs from capture world")
        return self
