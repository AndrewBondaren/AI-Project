"""Shared placement value types — tz_map_light_bake § Placement P1."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, StringConstraints


type PlacementUid = Annotated[StrictStr, StringConstraints(min_length=1, pattern=r"^\S(?:.*\S)?$")]
type PlacementText = Annotated[StrictStr, StringConstraints(min_length=1, pattern=r"\S")]
type NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
type Specificity = NonNegativeInt
type OriginalArea = Annotated[StrictFloat, Field(gt=0, allow_inf_nan=False)]
type FineCell = tuple[StrictInt, StrictInt]


class PlacementModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class PlacementMode(StrEnum):
    ABSOLUTE = "absolute"
    SEMANTIC = "semantic"


class AbsoluteMovement(StrEnum):
    FORBID = "forbid"
    EXPLICIT_CANDIDATES = "explicit_candidates"


class DependencyRelation(StrEnum):
    RESOLVED = "resolved"
    SUPPORTED_BY = "supported_by"
    CONTAINED_BY = "contained_by"
    CONNECTED_TO = "connected_to"


class OverlapRelation(StrEnum):
    COVERAGE = "coverage"
    CONTAINMENT = "containment"
    CONNECTION = "connection"
    EMBEDDING = "embedding"
    SHARED_BOUNDARY = "shared_boundary"


class PlacementPhase(StrEnum):
    PRE_RELIEF = "pre_relief"
    DEPENDENT = "dependent"


class WaterPresence(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"
