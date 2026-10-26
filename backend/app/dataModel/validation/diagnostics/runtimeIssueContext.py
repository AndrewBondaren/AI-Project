"""Typed runtime fallback provenance — GEO-1 §6.29 diagnostic contract."""

from enum import StrEnum
from typing import Annotated, Generic, TypeVar

from pydantic import ConfigDict, StrictInt, StrictStr, StringConstraints
from pydantic.dataclasses import dataclass

from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.facing import Facing


type RevisionHex = Annotated[StrictStr, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
A_co = TypeVar("A_co", bound=StrEnum, covariant=True)
R_co = TypeVar("R_co", bound=StrEnum, covariant=True)


@dataclass(frozen=True, config=ConfigDict(extra="forbid", strict=True, revalidate_instances="always"))
class RuntimeIssueContext(Generic[A_co, R_co]):
    world_uid: EntityUid
    snapshot_uid: EntityUid | None
    content_revision: RevisionHex | None
    source_uid: EntityUid | None
    body_uids: tuple[EntityUid, ...]
    cell: tuple[StrictInt, StrictInt] | None
    face: Facing | None
    fallback_action: A_co
    fallback_reason: R_co
