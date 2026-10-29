"""Hydrology-owned boundary contracts over the common placement lifecycle."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationInfo, field_validator, model_validator

from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.result import PlacementOutcomeV2, ResolvedPlacementV2
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.validation.immutableValue import validate_immutable

_UID = TypeAdapter(EntityUid)


class BoundaryIssueCode(StrEnum):
    INVALID_INPUT = "BOUNDARY_INVALID_INPUT"
    UNKNOWN_FINE_WATER = "BOUNDARY_UNKNOWN_FINE_WATER"
    BOUNDARY_OFF_TARGET = "BOUNDARY_OFF_TARGET"


class CoastlinePart(BaseModel, frozen=True):
    """One contiguous authored-path run associated with an actual physical body."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    body_uid: EntityUid
    closed: bool
    path: tuple[HydrologyWaypoint, ...] = Field(min_length=1)

    @field_validator("path", mode="before")
    @classmethod
    def normalized_points(cls, value: object, info: ValidationInfo) -> object:
        if info.mode == "json" and isinstance(value, list):
            value = tuple(value)
        if isinstance(value, tuple):
            return tuple(HydrologyWaypoint.model_validate(point.model_dump(warnings=False), strict=True)
                         if isinstance(point, HydrologyWaypoint) else point for point in value)
        return value

    @model_validator(mode="after")
    def immutable_part(self) -> Self:
        validate_immutable(self)
        return self


class AttachedCoastline(BaseModel, frozen=True):
    model_config = CoastlinePart.model_config

    source_uid: EntityUid
    target_source_uid: EntityUid
    parts: tuple[CoastlinePart, ...] = Field(min_length=1)
    coordinate_space: Literal[CoordinateSpace.WORLD_FINE_GRID]
    hydrology_ref: PlanRef


class CoastlineBoundaryInput(BaseModel, frozen=True):
    """Whole authored boundary scope, independent of requested output tiles."""

    model_config = CoastlinePart.model_config

    sources: tuple[DeclaredCoastline, ...]
    resolution_mode: ResolutionMode
    grid: SurfaceGridSettings
    topology: WorldTopology

    @field_validator("topology", mode="before")
    @classmethod
    def normalized_topology(cls, value: object) -> object:
        return WorldTopology.model_validate(value.model_dump(warnings=False), strict=True) if isinstance(value, WorldTopology) else value

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, value: object, info: ValidationInfo) -> object:
        if info.mode == "json" and isinstance(value, list):
            value = tuple(value)
        if isinstance(value, tuple):
            return tuple(DeclaredCoastline.model_validate(source.model_dump(warnings=False), strict=True)
                         if isinstance(source, DeclaredCoastline) else source for source in value)
        return value

    @model_validator(mode="after")
    def boundary_sources(self) -> Self:
        uids = tuple(_UID.validate_python(source.location_uid, strict=True) for source in self.sources)
        if len(set(uids)) != len(uids):
            raise ValueError("duplicate boundary source UID")
        if any(source.purpose is not CoastlinePurpose.BODY_BOUNDARY for source in self.sources):
            raise ValueError("boundary input accepts only BODY_BOUNDARY sources")
        validate_immutable(self)
        return self


class CoastlineBoundaryPlan(BaseModel, frozen=True):
    """Only accepted geometry is emitted; original domain issues remain available."""

    model_config = CoastlinePart.model_config

    boundaries: tuple[AttachedCoastline, ...]
    outcomes: tuple[PlacementOutcomeV2, ...]
    issues: tuple[FieldPathError, ...] = ()

    @model_validator(mode="after")
    def accepted_outputs(self) -> Self:
        emitted = tuple(boundary.source_uid for boundary in self.boundaries)
        expected = tuple(outcome.identity.source_uid for outcome in self.outcomes if isinstance(outcome, ResolvedPlacementV2))
        if len(set(emitted)) != len(emitted) or set(emitted) != set(expected):
            raise ValueError("boundary outputs must match resolved outcomes exactly")
        validate_immutable(self)
        return self
