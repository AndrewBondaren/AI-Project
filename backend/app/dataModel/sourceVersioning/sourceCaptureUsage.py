"""Declared dependencies of one capture; no full-read-set certificate."""

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
