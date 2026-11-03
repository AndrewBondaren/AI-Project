"""Adapter-prepared geometry and pre-carve facts, without carve or resolution."""

from enum import Enum
from typing import Literal, Self

from pydantic import Field, StrictInt, ValidatorFunctionWrapHandler, field_validator, model_validator

from app.dataModel.annotationPolicy import StrictEnumOnWire, StrictOnWire
from app.dataModel.placement.common import (
    AbsoluteMovement, FineCell, NonNegativeInt, OriginalArea, PlacementMode, PlacementModel,
    PlacementText, PlacementUid, Specificity, WaterPresence,
)
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision
from app.dataModel.policy.policyEnums import PolicyState


class PlacementFootprint(PlacementModel):
    cells: StrictOnWire[frozenset[FineCell]] = Field(min_length=1)
    z_min: StrictOnWire[StrictInt | None]
    z_max: StrictOnWire[StrictInt | None]

    @model_validator(mode="after")
    def ordered_vertical_extent(self) -> Self:
        if (self.z_min is None) != (self.z_max is None):
            raise ValueError("placement requires both z_min/z_max or neither")
        if self.z_min is not None and self.z_max is not None and self.z_min > self.z_max:
            raise ValueError("placement requires z_min <= z_max")
        return self


class PlacementCandidate(PlacementModel):
    candidate_uid: StrictOnWire[PlacementUid]
    preference: StrictOnWire[NonNegativeInt]
    footprint: StrictOnWire[PlacementFootprint]


class CapturedPlacementGeometry(PlacementModel):
    """Fine geometry supplied by the owner before placement admission."""

    model_config = {**PlacementModel.model_config, "strict": True}
    coordinate_space: Literal[CoordinateSpace.WORLD_FINE_GRID]
    pre_hydrology_ref: PlanRef
    intent: PlacementIntent
    original_area: OriginalArea
    candidates: tuple[PlacementCandidate, ...] = Field(min_length=1)

    @field_validator("coordinate_space", mode="before")
    @classmethod
    def fine_frame(cls, value: object) -> CoordinateSpace:
        if value is not CoordinateSpace.WORLD_FINE_GRID:
            raise ValueError("captured placement geometry requires world fine grid")
        return value

    @field_validator("original_area", mode="before")
    @classmethod
    def discrete_area(cls, value: object) -> float:
        if type(value) not in (int, float) or not 0 < value <= 2**53 or not float(value).is_integer():
            raise ValueError("original area must be an exact positive fine cell count up to 2**53")
        return float(value)

    @model_validator(mode="after")
    def consistent_capture(self) -> Self:
        if self.intent.identity.world_uid != self.pre_hydrology_ref.key.world_uid:
            raise ValueError("captured intent and pre-water revision must belong to the same world")
        if len({c.candidate_uid for c in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate placement candidate_uid")
        if (self.intent.mode is PlacementMode.ABSOLUTE and self.intent.absolute_movement is AbsoluteMovement.FORBID
                and len(self.candidates) > 1):
            raise ValueError("absolute alternatives require explicit_candidates movement policy")
        return self


# GEO-LEGACY-01: Retire V1 preparation and its coastline decision.
class CoastlinePlacementFact(PlacementModel):
    snapshot_uid: StrictOnWire[PlacementUid]
    water_presence: StrictEnumOnWire[WaterPresence]
    reason: StrictOnWire[PlacementText]


# GEO-LEGACY-01: Retire V1 preparation and its coastline decision.
class PreparedPlacement(PlacementModel):
    intent: StrictOnWire[PlacementIntent]
    original_area: StrictOnWire[OriginalArea]
    candidates: StrictOnWire[tuple[PlacementCandidate, ...]]
    auto_specificity: StrictOnWire[Specificity | None]
    coastline: StrictOnWire[CoastlinePlacementFact | None]

    @model_validator(mode="after")
    def valid_candidates(self) -> Self:
        uids = [candidate.candidate_uid for candidate in self.candidates]
        if len(uids) != len(set(uids)):
            raise ValueError("duplicate placement candidate_uid")
        if (self.intent.mode == PlacementMode.ABSOLUTE
                and self.intent.absolute_movement == AbsoluteMovement.FORBID
                and len(self.candidates) > 1):
            raise ValueError("absolute alternatives require explicit_candidates movement policy")
        return self

    @property
    def effective_specificity(self) -> int | None:
        """Schema policy only; None remains unresolved, never an error default."""
        if self.coastline is not None:
            if self.coastline.water_presence == WaterPresence.UNKNOWN:
                return None
            if self.coastline.water_presence == WaterPresence.ABSENT:
                return 0
        authored = self.intent.placement_specificity
        return authored if authored is not None else self.auto_specificity


class PreparedPlacementV2(PlacementModel):
    """G0-P target: preparation consumes a ready decision, never resolves it."""

    intent: PlacementIntent
    original_area: OriginalArea
    candidates: tuple[PlacementCandidate, ...]
    decision: ObjectAdmissionDecision[Enum, Enum]

    @field_validator("original_area", mode="wrap")
    @classmethod
    def preserve_integer_area(cls, value: object, validate: ValidatorFunctionWrapHandler) -> float:
        area = validate(value)
        if isinstance(value, int) and area != value:
            raise ValueError("original area loses integer precision")
        return area

    @model_validator(mode="after")
    def ready_geometry(self) -> Self:
        if self.decision.state is not PolicyState.READY:
            raise ValueError("only ready admission can prepare geometry")
        uids = [c.candidate_uid for c in self.candidates]
        if len(uids) != len(set(uids)):
            raise ValueError("duplicate placement candidate_uid")
        if (self.intent.mode is PlacementMode.ABSOLUTE and self.intent.absolute_movement is AbsoluteMovement.FORBID
                and len(self.candidates) > 1):
            raise ValueError("absolute alternatives require explicit_candidates movement policy")
        return self

    @property
    def effective_specificity(self) -> int:
        priority = self.decision.effective_priority
        if priority is None or priority <= 0:
            raise ValueError("ready prepared placement requires positive priority")
        return priority
