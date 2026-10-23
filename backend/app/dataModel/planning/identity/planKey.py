"""Planning lookup identity — tz_terrain_generation PC-0/PC-A."""

from enum import StrEnum
from typing import Annotated, Literal, NewType

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid


InputFingerprint = NewType("InputFingerprint", bytes)
OutputFingerprint = NewType("OutputFingerprint", bytes)
StateViewRevision = NewType("StateViewRevision", bytes)
AlgorithmVersion = NewType("AlgorithmVersion", int)
SchemaVersion = NewType("SchemaVersion", int)
PlanSlot = NewType("PlanSlot", str)

# Version definitions precede metadata: both public modules can be imported first.
from app.dataModel.planning.contracts.planContract import PlanContractId


class PlanScopeKind(StrEnum):
    WORLD = "world"
    REGION = "region"


class WorldPlanScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[PlanScopeKind.WORLD] = PlanScopeKind.WORLD


class RegionPlanScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    kind: Literal[PlanScopeKind.REGION] = PlanScopeKind.REGION
    region_uid: EntityUid


type PlanScope = Annotated[WorldPlanScope | RegionPlanScope, Field(discriminator="kind")]


class PlanKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    world_uid: EntityUid
    scope: PlanScope
    contract_id: PlanContractId
    schema_version: SchemaVersion = Field(strict=True, gt=0)
    algorithm_version: AlgorithmVersion = Field(strict=True, gt=0)
    input_fingerprint: InputFingerprint = Field(strict=True, min_length=32, max_length=32)
