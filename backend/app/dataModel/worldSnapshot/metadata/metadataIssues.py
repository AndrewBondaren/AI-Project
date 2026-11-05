"""Snapshot metadata diagnostics produced before envelope construction."""
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef


class SnapshotMetadataCode(StrEnum):
    INVALID_TURN_ID = "snapshot.metadata.invalid_turn_id"
    INVALID_CREATED_AT = "snapshot.metadata.invalid_created_at"
    DUPLICATE_EXPECTATION = "snapshot.metadata.duplicate_expectation"
    UNEXPECTED_PLAYER = "snapshot.metadata.unexpected_player"
    MISSING_PLAYER = "snapshot.metadata.missing_player"
    SELF_PARENT = "snapshot.metadata.self_parent"
    MISSING_BASE = "snapshot.metadata.missing_base"
    BASE_IDENTITY = "snapshot.metadata.base_identity"
    UNEXPECTED_BASE = "snapshot.metadata.unexpected_base"
    FOREIGN_DESTINATION = "snapshot.metadata.foreign_destination"
    INVALID_RETENTION = "snapshot.metadata.invalid_retention"
    INVALID_ARTIFACT = "snapshot.metadata.invalid_artifact"
    DUPLICATE_ARTIFACT = "snapshot.metadata.duplicate_artifact"
    INVALID_RECEIPTS = "snapshot.metadata.invalid_receipts"
    INVALID_RECEIPT = "snapshot.metadata.invalid_receipt"
    DUPLICATE_SECTION = "snapshot.metadata.duplicate_section"
    FOREIGN_OPERATION = "snapshot.metadata.foreign_operation"
    UNASSIGNED_ARTIFACT = "snapshot.metadata.unassigned_artifact"
    FOREIGN_HISTORY = "snapshot.metadata.foreign_history"
    NOOP_STATE = "snapshot.metadata.noop_state"
    SUPERSEDED_STATE = "snapshot.metadata.superseded_state"
    UNREACHABLE_STATE = "snapshot.metadata.unreachable_state"
    MISSING_PACK = "snapshot.metadata.missing_pack"
    MISSING_PERSISTED_BASE = "snapshot.metadata.missing_persisted_base"


class SnapshotMetadataFieldIssue(FieldPathError[SnapshotMetadataCode]):
    location: Literal["receipts", "retained"]
    destination: tuple[Annotated[int, Field(ge=0)]] | tuple[str, Annotated[int, Field(ge=0)]]

    @property
    def diagnostic_path(self) -> tuple[str | int, ...]:
        return (self.location, *self.destination, *self.path.projection())


class SnapshotMetadataRelationIssue(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    code: SnapshotMetadataCode
    location: Literal["receipts", "retained", "parents", "bases", "validation", "context",
                      "player_snapshots", "turn_id", "created_at"]
    address: tuple[str | int, ...]
    snapshot: SnapshotRef | None = None
    message: str

    @property
    def diagnostic_path(self) -> tuple[str | int, ...]:
        return (self.location, *self.address)


type SnapshotBuilderIssue = SnapshotMetadataFieldIssue | SnapshotMetadataRelationIssue
