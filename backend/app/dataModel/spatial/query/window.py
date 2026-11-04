"""Canonical, half-open windows in the prepared fine-grid frame."""
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


class SpatialBox(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    x0: FineX
    x1: FineX
    y0: FineY
    y1: FineY
    z0: FineZ
    z1: FineZ

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.x0 >= self.x1 or self.y0 >= self.y1 or self.z0 >= self.z1:
            raise ValueError("empty or reversed spatial box")
        return self


class SpatialWindow(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    space: Literal[CoordinateSpace.WORLD_FINE_GRID]
    topology: WorldTopology
    boxes: tuple[SpatialBox, ...] = Field(min_length=1)

    @field_validator("space", mode="before")
    @classmethod
    def fine_space(cls, value: object) -> object:
        if value is not CoordinateSpace.WORLD_FINE_GRID:
            raise ValueError("expected the world fine grid")
        return value

    @field_validator("topology", mode="before")
    @classmethod
    def prepared_frame(cls, value: object) -> WorldTopology:
        if not isinstance(value, WorldTopology) or not isinstance(getattr(value, "mode", None), WorldTopologyMode):
            raise ValueError("expected a prepared world topology")
        bounds = getattr(value, "bounds", None)
        if not isinstance(bounds, WorldBounds):
            raise ValueError("expected world bounds")
        if any(type(getattr(bounds, name, None)) is not int for name in WorldBounds.model_fields):
            raise ValueError("expected integer bounds")
        if bounds.x_min > bounds.x_max or bounds.y_min > bounds.y_max:
            raise ValueError("reversed world bounds")
        if value.mode is WorldTopologyMode.SPHERE and (bounds.x_max - bounds.x_min + 1) % 2:
            raise ValueError("odd sphere width")
        return value

    @model_validator(mode="after")
    def canonical_union(self) -> Self:
        bounds = self.topology.bounds
        previous = None
        active: list[SpatialBox] = []
        for box in self.boxes:
            if not (bounds.x_min <= box.x0 < box.x1 <= bounds.x_max + 1
                    and bounds.y_min <= box.y0 < box.y1 <= bounds.y_max + 1):
                raise ValueError("spatial box outside canonical frame")
            key = (box.y0, box.x0, box.z0, box.y1, box.x1, box.z1)
            if previous is not None and key <= previous:
                raise ValueError("spatial boxes out of canonical order")
            active = [other for other in active if other.y1 > box.y0]
            if any(other.x0 < box.x1 and box.x0 < other.x1 and other.z0 < box.z1 and box.z0 < other.z1
                   for other in active):
                raise ValueError("overlapping spatial boxes")
            active.append(box)
            previous = key
        return self
