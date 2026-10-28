"""Final fill's many-to-many source/body evidence, never inferred from equal UIDs."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.identity.uid import EntityUid


class SourceBodyMappingEntry(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    source_uid: EntityUid
    # An explicit empty tuple is authoritative dry evidence for this source.
    body_uids: tuple[EntityUid, ...]

    @model_validator(mode="after")
    def canonical_bodies(self) -> Self:
        if self.body_uids != tuple(sorted(set(self.body_uids))):
            raise ValueError("body UIDs must be sorted and unique")
        return self


class SourceBodyMapping(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    entries: tuple[SourceBodyMappingEntry, ...]

    @model_validator(mode="after")
    def canonical_sources(self) -> Self:
        uids = tuple(entry.source_uid for entry in self.entries)
        if uids != tuple(sorted(set(uids))):
            raise ValueError("source UIDs must be sorted and unique")
        return self
