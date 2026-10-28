"""Captured terrain constraints; neither source settings nor accepted placement."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSource
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable


class WaterDesignConstraints(BaseModel, frozen=True):
    """Allowed coarse cells and the required strip, bound to captured source/ref/scale."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    source: WaterDesignSource
    pre_hydrology_ref: PlanRef
    grid: SurfaceGridSettings
    allowed_cells: frozenset[Coord] = Field(min_length=1)
    required_cells: frozenset[Coord] = Field(min_length=1)
    notices: tuple[FieldPathError, ...]

    @model_validator(mode="after")
    def complete_constraints(self) -> Self:
        if not self.required_cells <= self.allowed_cells:
            raise ValueError("required cells must be inside the allowed mask")
        validate_immutable(self)
        return self
