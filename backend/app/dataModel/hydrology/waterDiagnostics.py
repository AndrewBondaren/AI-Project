"""Hydrology-owned facts emitted while assembling water."""
from enum import StrEnum
from typing import Annotated, ClassVar, Literal, Self, get_args

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SerializeAsAny, StrictInt, StrictStr, field_validator, model_validator

from app.dataModel.hydrology.waterKindMismatchIssue import WaterKindMismatchIssue
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition, require_concrete_diagnostic


class WaterDiagnosticCode(StrEnum):
    WATER_PUDDLE = "WATER_PUDDLE"
    WATER_CANNOT_HOLD = "WATER_CANNOT_HOLD"
    WATER_TERRAIN_UNRESOLVED = "WATER_TERRAIN_UNRESOLVED"
    WATER_NO_OCEAN_DEPRESSION = "WATER_NO_OCEAN_DEPRESSION"
    WATER_LEVEL_SPILL = "WATER_LEVEL_SPILL"
    WATER_LEVEL_SUPERSEDED = "WATER_LEVEL_SUPERSEDED"
    WATER_WORLD_OCEAN = "WATER_WORLD_OCEAN"
    WATER_PLACEMENT_REQUIRED = "WATER_PLACEMENT_REQUIRED"


type Count = Annotated[StrictInt, Field(ge=0)]
type PositiveCount = Annotated[StrictInt, Field(gt=0)]


class _WaterFact(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    @field_validator("code", mode="before", check_fields=False)
    @classmethod
    def require_code(cls, value: object) -> object:
        if type(value) is not WaterDiagnosticCode:
            raise ValueError("expected WaterDiagnosticCode")
        return value


class WaterPuddle(_WaterFact):
    code: Literal[WaterDiagnosticCode.WATER_PUDDLE]
    source_uid: EntityUid
    cell_count: Count
    minimum_cells: PositiveCount

    @model_validator(mode="after")
    def check_component_size(self) -> Self:
        if self.cell_count >= self.minimum_cells:
            raise ValueError("puddle requires fewer cells than the minimum")
        return self


class WaterCannotHold(_WaterFact):
    code: Literal[WaterDiagnosticCode.WATER_CANNOT_HOLD]
    source_uid: EntityUid
    effective_level: StrictInt


class WaterTerrainUnresolved(_WaterFact):
    code: Literal[WaterDiagnosticCode.WATER_TERRAIN_UNRESOLVED]
    world_uid: EntityUid
    message: StrictStr


class WaterNoOceanDepression(_WaterFact):
    code: Literal[WaterDiagnosticCode.WATER_NO_OCEAN_DEPRESSION]
    world_uid: EntityUid
    default_water_level: StrictInt


class WaterLevelSpill(_WaterFact):
    code: Literal[WaterDiagnosticCode.WATER_LEVEL_SPILL]
    source_uid: EntityUid
    requested_level: StrictInt
    spill_limited_level: StrictInt

    @model_validator(mode="after")
    def check_spill_reduces_level(self) -> Self:
        if self.spill_limited_level >= self.requested_level:
            raise ValueError("spill requires a reduced level")
        return self


class WaterLevelSuperseded(_WaterFact):
    code: Literal[WaterDiagnosticCode.WATER_LEVEL_SUPERSEDED]
    source_uid: EntityUid
    declared_level: StrictInt
    effective_level: StrictInt
    parent_system_uid: EntityUid | None

    @model_validator(mode="after")
    def check_effective_level_changed(self) -> Self:
        if self.declared_level == self.effective_level:
            raise ValueError("superseded levels must differ")
        return self


class WaterWorldOcean(_WaterFact):
    code: Literal[WaterDiagnosticCode.WATER_WORLD_OCEAN]
    world_uid: EntityUid
    water_cells: Count
    world_cells: PositiveCount

    @model_validator(mode="after")
    def check_coverage(self) -> Self:
        if 2 * self.water_cells < self.world_cells:
            raise ValueError("world ocean requires at least half the world covered")
        return self


class WaterPlacementRequired(_WaterFact):
    code: Literal[WaterDiagnosticCode.WATER_PLACEMENT_REQUIRED]
    world_uid: EntityUid


class _WaterDisposition:
    expected_disposition: ClassVar[PlanDiagnosticDisposition]

    @field_validator("disposition")
    @classmethod
    def check_disposition(cls, value: PlanDiagnosticDisposition) -> PlanDiagnosticDisposition:
        if value is not cls.expected_disposition:
            raise ValueError("disposition does not match water fact")
        return value


class WaterPuddleDiagnostic(_WaterDisposition, PlanDiagnostic[WaterPuddle]):
    issue: SerializeAsAny[WaterPuddle]
    expected_disposition: ClassVar[PlanDiagnosticDisposition] = PlanDiagnosticDisposition.ERROR


class WaterCannotHoldDiagnostic(_WaterDisposition, PlanDiagnostic[WaterCannotHold]):
    issue: SerializeAsAny[WaterCannotHold]
    expected_disposition: ClassVar[PlanDiagnosticDisposition] = PlanDiagnosticDisposition.ERROR


class WaterTerrainUnresolvedDiagnostic(_WaterDisposition, PlanDiagnostic[WaterTerrainUnresolved]):
    issue: SerializeAsAny[WaterTerrainUnresolved]
    expected_disposition: ClassVar[PlanDiagnosticDisposition] = PlanDiagnosticDisposition.ERROR


class WaterNoOceanDepressionDiagnostic(_WaterDisposition, PlanDiagnostic[WaterNoOceanDepression]):
    issue: SerializeAsAny[WaterNoOceanDepression]
    expected_disposition: ClassVar[PlanDiagnosticDisposition] = PlanDiagnosticDisposition.ERROR


class WaterLevelSpillDiagnostic(_WaterDisposition, PlanDiagnostic[WaterLevelSpill]):
    issue: SerializeAsAny[WaterLevelSpill]
    expected_disposition: ClassVar[PlanDiagnosticDisposition] = PlanDiagnosticDisposition.FALLBACK


class WaterLevelSupersededDiagnostic(_WaterDisposition, PlanDiagnostic[WaterLevelSuperseded]):
    issue: SerializeAsAny[WaterLevelSuperseded]
    expected_disposition: ClassVar[PlanDiagnosticDisposition] = PlanDiagnosticDisposition.FALLBACK


class WaterWorldOceanDiagnostic(_WaterDisposition, PlanDiagnostic[WaterWorldOcean]):
    issue: SerializeAsAny[WaterWorldOcean]
    expected_disposition: ClassVar[PlanDiagnosticDisposition] = PlanDiagnosticDisposition.NOTICE


class WaterPlacementRequiredDiagnostic(_WaterDisposition, PlanDiagnostic[WaterPlacementRequired]):
    issue: SerializeAsAny[WaterPlacementRequired]
    expected_disposition: ClassVar[PlanDiagnosticDisposition] = PlanDiagnosticDisposition.ERROR


type WaterOperationalFact = (
    WaterPuddle
    | WaterCannotHold
    | WaterTerrainUnresolved
    | WaterNoOceanDepression
    | WaterLevelSpill
    | WaterLevelSuperseded
    | WaterWorldOcean
    | WaterPlacementRequired
)
type WaterPlanningDiagnostic = (
    PlanDiagnostic
    | WaterPuddleDiagnostic
    | WaterCannotHoldDiagnostic
    | WaterTerrainUnresolvedDiagnostic
    | WaterNoOceanDepressionDiagnostic
    | WaterLevelSpillDiagnostic
    | WaterLevelSupersededDiagnostic
    | WaterWorldOceanDiagnostic
)


_REPORT_TYPES = (*get_args(WaterPlanningDiagnostic.__value__), WaterPlacementRequiredDiagnostic)


def require_water_diagnostic(value: object) -> WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic:
    diagnostic = require_concrete_diagnostic(value)
    if type(diagnostic) not in _REPORT_TYPES:
        raise ValueError("expected a water diagnostic")
    if type(diagnostic) is PlanDiagnostic and type(diagnostic.issue) is not WaterKindMismatchIssue:
        raise ValueError("water field diagnostic requires a kind mismatch issue")
    if type(diagnostic) is PlanDiagnostic and diagnostic.disposition is not PlanDiagnosticDisposition.FALLBACK:
        raise ValueError("water kind mismatch requires FALLBACK")
    return diagnostic


type ReportDiagnostic = Annotated[
    WaterPlanningDiagnostic | WaterPlacementRequiredDiagnostic, BeforeValidator(require_water_diagnostic)
]


class WaterDiagnosticReport(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    ordered: tuple[ReportDiagnostic, ...]
    blocking: tuple[ReportDiagnostic, ...]
    continuations: tuple[Annotated[WaterPlanningDiagnostic, BeforeValidator(require_water_diagnostic)], ...]
    notices: tuple[Annotated[WaterWorldOceanDiagnostic, BeforeValidator(require_water_diagnostic)], ...]

    @model_validator(mode="after")
    def check_dispositions(self) -> Self:
        for group, disposition in ((self.blocking, PlanDiagnosticDisposition.ERROR),
                                   (self.continuations, PlanDiagnosticDisposition.FALLBACK),
                                   (self.notices, PlanDiagnosticDisposition.NOTICE)):
            if group != tuple(item for item in self.ordered if item.disposition is disposition):
                raise ValueError("water diagnostic group differs from ordered diagnostics")
        return self

    @classmethod
    def empty(cls) -> Self:
        return cls(ordered=(), blocking=(), continuations=(), notices=())
