"""World/player history identities; no lookup, allocation or persistence."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid


class SnapshotChainKind(StrEnum):
    WORLD = "world"
    PLAYER = "player"


class WorldSnapshotRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[SnapshotChainKind.WORLD] = SnapshotChainKind.WORLD
    world_uid: EntityUid
    timeline_id: EntityUid
    snapshot_id: EntityUid


class PlayerSnapshotRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[SnapshotChainKind.PLAYER] = SnapshotChainKind.PLAYER
    player_uid: EntityUid
    snapshot_id: EntityUid


type SnapshotRef = Annotated[WorldSnapshotRef | PlayerSnapshotRef, Field(discriminator="kind")]
