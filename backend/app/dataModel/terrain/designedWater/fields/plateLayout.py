"""Derived plate centers and affine provenance; the recipe remains the settings owner."""

from math import gcd
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.terrain.designedWater.fields.field import ContinentalFieldValue, PlateRecipe
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable


class PlateCenter(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    index: StrictInt = Field(ge=0)
    cell: FineXY
    buoyancy: ContinentalFieldValue


class PlateLayout(BaseModel, frozen=True):
    """An immutable derived sampler input; no replacement authored plate_count."""

    model_config = PlateCenter.model_config

    recipe: PlateRecipe
    multiplier: StrictInt = Field(ge=1)
    offset: StrictInt = Field(ge=0)
    centers: tuple[PlateCenter, ...] = Field(min_length=1)
    notices: tuple[FieldPathError, ...]

    @property
    def effective_count(self) -> int:
        return len(self.centers)

    @model_validator(mode="after")
    def canonical_permutation(self) -> Self:
        bounds = self.recipe.topology.bounds
        size = bounds.width * bounds.height
        if size == 1:
            if (self.multiplier, self.offset) != (1, 0):
                raise ValueError("one-cell plate layout requires a=1,b=0")
        elif self.multiplier >= size or self.offset >= size or gcd(self.multiplier, size) != 1:
            raise ValueError("plate coefficients must define a permutation of canonical fine cells")
        count = min(self.recipe.plate_policy.plate_count, size)
        if len(self.centers) != count or tuple(center.index for center in self.centers) != tuple(range(count)):
            raise ValueError("plate centers must cover the effective indexed prefix")
        for center in self.centers:
            position = (self.multiplier * center.index + self.offset) % size
            expected = (bounds.x_min + position % bounds.width, bounds.y_min + position // bounds.width)
            if center.cell != expected:
                raise ValueError("plate center does not match its canonical permutation index")
        validate_immutable(self)
        return self
