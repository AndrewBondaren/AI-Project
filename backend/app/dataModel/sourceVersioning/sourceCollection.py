"""Membership value; descriptor-aware ordering/admission belongs to application."""

# TODO(SOURCE-TYPED-ERRORS): Semantic diagnostics at the Source boundary remain
# OPEN; see .cursor/plans/source-g1-values-canonical-implementation.md §3.

from typing import Self

from pydantic import model_validator

from app.dataModel.sourceVersioning._value import SourceValue
from app.dataModel.sourceVersioning.sourceObjectId import LibraryMemberId, SourceCollectionId, SourceObjectId


class SourceCollectionBody(SourceValue, frozen=True):
    collection: SourceCollectionId
    members: tuple[SourceObjectId, ...]

    @model_validator(mode="after")
    def membership_shape(self) -> Self:
        if len(set(self.members)) != len(self.members):
            raise ValueError("duplicate collection member identity")
        if any(not isinstance(member, LibraryMemberId) and member.world_uid != self.collection.world_uid
               for member in self.members):
            raise ValueError("member world differs from collection world")
        return self
