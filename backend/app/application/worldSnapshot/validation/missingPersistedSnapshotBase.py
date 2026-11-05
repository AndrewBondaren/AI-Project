"""Pinned snapshot absent from storage during metadata publication."""
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.metadata.metadataIssues import SnapshotMetadataCode


class MissingPersistedSnapshotBase(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    code: Literal[SnapshotMetadataCode.MISSING_PERSISTED_BASE] = SnapshotMetadataCode.MISSING_PERSISTED_BASE
    snapshot: SnapshotRef
    player_index: Annotated[int, Field(ge=0)] | None

    @model_validator(mode="after")
    def check_source(self) -> Self:
        if isinstance(self.snapshot, WorldSnapshotRef) != (self.player_index is None):
            raise ValueError("player index must identify the expected player head")
        return self

    @property
    def diagnostic_path(self) -> tuple[str | int, ...]:
        if self.player_index is None:
            return ("validation", "expected_world", "snapshot_head")
        return ("validation", "expected_players", self.player_index, "expected_head")

    @property
    def message(self) -> str:
        return f"missing pinned snapshot {self.snapshot.snapshot_id}"
