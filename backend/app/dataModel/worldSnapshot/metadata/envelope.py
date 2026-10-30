"""Immutable history envelopes; publication assigns identities and timestamps."""

from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.values import FormatVersion
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef


def _validate_created_at(value: str) -> str:
    # Parsing is pure calendar validation, never a clock read or timezone conversion.
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    return value


type CreatedAtUtc = Annotated[
    StrictStr, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$"),
    AfterValidator(_validate_created_at),
]


class WorldSnapshotMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    ref: WorldSnapshotRef
    parent: WorldSnapshotRef | None
    operation_id: EntityUid
    turn_id: Annotated[StrictInt, Field(ge=1)]
    created_at: CreatedAtUtc
    envelope_format_version: FormatVersion
    base_pack_hash: RevisionHex
    state_refs: tuple[SectionStateRef, ...]
    history_refs: tuple[SectionHistoryRef, ...]
    retained_artifacts: tuple[ArtifactRef, ...]

    @model_validator(mode="after")
    def coherent_envelope(self) -> Self:
        if self.parent is not None:
            if self.parent.world_uid != self.ref.world_uid or self.parent == self.ref:
                raise ValueError("parent must be a different snapshot of this world")
        for refs in (self.state_refs, self.history_refs):
            if len({ref.section_key for ref in refs}) != len(refs):
                raise ValueError("duplicate section key")
            for entry in refs:
                if not isinstance(entry.snapshot, WorldSnapshotRef) or entry.snapshot.world_uid != self.ref.world_uid:
                    raise ValueError("section belongs to another snapshot chain")
        if any(entry.snapshot != self.ref for entry in self.history_refs):
            raise ValueError("history must describe this snapshot")
        if len(set(self.retained_artifacts)) != len(self.retained_artifacts):
            raise ValueError("duplicate retained artifact")
        return self


class PlayerSnapshotMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    ref: PlayerSnapshotRef
    parent: PlayerSnapshotRef | None
    operation_id: EntityUid
    turn_id: Annotated[StrictInt, Field(ge=1)]
    created_at: CreatedAtUtc
    envelope_format_version: FormatVersion
    state_refs: tuple[SectionStateRef, ...]
    history_refs: tuple[SectionHistoryRef, ...]
    retained_artifacts: tuple[ArtifactRef, ...]

    @model_validator(mode="after")
    def coherent_envelope(self) -> Self:
        if self.parent is not None:
            if self.parent.player_uid != self.ref.player_uid or self.parent == self.ref:
                raise ValueError("parent must be a different snapshot of this player")
        for refs in (self.state_refs, self.history_refs):
            if len({ref.section_key for ref in refs}) != len(refs):
                raise ValueError("duplicate section key")
            for entry in refs:
                if not isinstance(entry.snapshot, PlayerSnapshotRef) or entry.snapshot.player_uid != self.ref.player_uid:
                    raise ValueError("section belongs to another snapshot chain")
        if any(entry.snapshot != self.ref for entry in self.history_refs):
            raise ValueError("history must describe this snapshot")
        if len(set(self.retained_artifacts)) != len(self.retained_artifacts):
            raise ValueError("duplicate retained artifact")
        return self


type SnapshotEnvelope = WorldSnapshotMetadata | PlayerSnapshotMetadata
