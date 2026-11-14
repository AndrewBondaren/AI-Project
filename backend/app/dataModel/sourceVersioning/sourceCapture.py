"""Capture mappings, not proof of finalization or availability of decoded bodies."""

# TODO(SOURCE-TYPED-ERRORS): Semantic diagnostics at the Source boundary remain
# OPEN; see .cursor/plans/source-g1-values-canonical-implementation.md §3.

from typing import Self

from pydantic import model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceBodyVersion import SourceBodyVersion, SourceCollectionVersion
from app.dataModel.sourceVersioning.sourceObjectId import LibraryMemberId


class SourceCapture(SourceValue, frozen=True):
    world_uid: EntityUid
    objects: tuple[SourceBodyVersion, ...]
    collections: tuple[SourceCollectionVersion, ...]

    @model_validator(mode="after")
    def mapping_shape(self) -> Self:
        objects = tuple(item.source.object_id for item in self.objects)
        collections = tuple(item.source.collection_id for item in self.collections)
        if len(set(objects)) != len(objects) or len(set(collections)) != len(collections):
            raise ValueError("capture requires one revision per identity")
        if any(not isinstance(identity, LibraryMemberId) and identity.world_uid != self.world_uid
               for identity in objects) or any(identity.world_uid != self.world_uid for identity in collections):
            raise ValueError("mapping world differs from capture world")
        return self
