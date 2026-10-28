"""Absolute floor payloads; evaluation and height writes belong to terrain application."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.designedWater.fields.field import WaterFieldRecipe
from app.dataModel.topology.worldTopology import Coord


class FloorProfileKind(StrEnum):
    SAMPLED = "sampled"
    FIELD = "field"


class SampledFloorProfile(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    kind: Literal[FloorProfileKind.SAMPLED] = FloorProfileKind.SAMPLED
    space: CoordinateSpace
    samples: tuple[tuple[Coord, FineZ], ...]

    @model_validator(mode="after")
    def ordered_unique_samples(self) -> Self:
        keys = tuple((coord[1], coord[0]) for coord, _ in self.samples)
        if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
            raise ValueError("floor samples require unique coordinates in row-major order")
        # Footprint completeness and z < level belong to the enclosing draft/spec.
        return self


class FieldFloorProfile(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    kind: Literal[FloorProfileKind.FIELD] = FloorProfileKind.FIELD
    recipe: WaterFieldRecipe
    level: FineZ
    depth: StrictInt = Field(gt=0)
    z_min: FineZ

    @model_validator(mode="after")
    def floor_is_possible(self) -> Self:
        if self.level <= self.z_min:
            raise ValueError("field floor requires level > z_min")
        return self


type BasinFloorProfile = Annotated[SampledFloorProfile | FieldFloorProfile, Field(discriminator="kind")]
