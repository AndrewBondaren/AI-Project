"""Adapter-prepared geometry and pre-carve facts, without carve or resolution."""

from typing import Self

from pydantic import Field, StrictInt, model_validator

from app.dataModel.annotationPolicy import StrictEnumOnWire, StrictOnWire
from app.dataModel.placement.common import (
    AbsoluteMovement, FineCell, NonNegativeInt, OriginalArea, PlacementMode, PlacementModel,
    PlacementText, PlacementUid, Specificity, WaterPresence,
)
from app.dataModel.placement.intent import PlacementIntent


class PlacementFootprint(PlacementModel):
    cells: StrictOnWire[frozenset[FineCell]] = Field(min_length=1)
    z_min: StrictOnWire[StrictInt | None]
    z_max: StrictOnWire[StrictInt | None]

    @model_validator(mode="after")
    def ordered_vertical_extent(self) -> Self:
        if (self.z_min is None) != (self.z_max is None):
            raise ValueError("placement requires both z_min/z_max or neither")
        if self.z_min is not None and self.z_min > self.z_max:
            raise ValueError("placement requires z_min <= z_max")
        return self


class PlacementCandidate(PlacementModel):
    candidate_uid: StrictOnWire[PlacementUid]
    preference: StrictOnWire[NonNegativeInt]
    footprint: StrictOnWire[PlacementFootprint]


class CoastlinePlacementFact(PlacementModel):
    snapshot_uid: StrictOnWire[PlacementUid]
    water_presence: StrictEnumOnWire[WaterPresence]
    reason: StrictOnWire[PlacementText]


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
