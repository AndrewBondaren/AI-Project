"""Runtime target expectations; lookup and overlap semantics belong to domains."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef


class RuntimeVersionKind(StrEnum):
    PACK = "pack"
    SNAPSHOT = "snapshot"


class PackTargetVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[RuntimeVersionKind.PACK] = RuntimeVersionKind.PACK
    pack_hash: RevisionHex
    artifact: ArtifactRef


class SnapshotTargetVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[RuntimeVersionKind.SNAPSHOT] = RuntimeVersionKind.SNAPSHOT
    snapshot: SnapshotRef


type RuntimeTargetVersion = Annotated[PackTargetVersion | SnapshotTargetVersion, Field(discriminator="kind")]


class TargetExpectationKind(StrEnum):
    ABSENT = "absent"
    VERSION = "version"


class TargetPresence(StrEnum):
    PRESENT = "present"
    DELETED = "deleted"


class TargetAbsent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[TargetExpectationKind.ABSENT] = TargetExpectationKind.ABSENT


class TargetVersionExpected(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[TargetExpectationKind.VERSION] = TargetExpectationKind.VERSION
    version: RuntimeTargetVersion
    presence: TargetPresence


type RuntimeTargetExpectation = Annotated[TargetAbsent | TargetVersionExpected, Field(discriminator="kind")]
