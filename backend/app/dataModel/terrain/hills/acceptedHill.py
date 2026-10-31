"""Realized hill geometry and its immutable spatial selection tree."""
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.hillShape import HillShape


class AcceptedHill(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    origin: FineXY
    radius: StrictInt = Field(gt=0)
    height: StrictInt = Field(gt=0)
    shape: HillShape
    axis: Literal[0, 1]

    @field_validator("axis", mode="before")
    @classmethod
    def integer_axis(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("hill axis must be an integer")
        return value


class HillLayout(BaseModel):
    """One hill per leaf; bounds conservatively contain all raster cells."""

    model_config = AcceptedHill.model_config

    bounds: GridBBox
    hill: AcceptedHill | None
    left: "HillLayout | None"
    right: "HillLayout | None"

    @model_validator(mode="after")
    def exact_bounds(self) -> Self:
        if self.hill is not None:
            if self.left is not None or self.right is not None:
                raise ValueError("hill leaf cannot have children")
            x, y = self.hill.origin
            r = self.hill.radius
            expected = GridBBox(x-r, x+r, y-r, y+r)
        else:
            if self.left is None or self.right is None:
                raise ValueError("hill branch requires both children")
            a, b = self.left.bounds, self.right.bounds
            expected = GridBBox(min(a.x_min, b.x_min), max(a.x_max, b.x_max),
                                min(a.y_min, b.y_min), max(a.y_max, b.y_max))
        if self.bounds != expected:
            raise ValueError("hill spatial bounds must match their contents")
        return self
