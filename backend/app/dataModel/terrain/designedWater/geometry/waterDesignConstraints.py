"""Captured terrain constraints; neither source settings nor accepted placement."""

from typing import Generic, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSource
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable


Cell = TypeVar("Cell", bound=Coord)


class _Constraints(BaseModel, Generic[Cell], frozen=True):

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    source: WaterDesignSource
    pre_hydrology_ref: PlanRef
    grid: SurfaceGridSettings
    allowed_cells: frozenset[Cell] = Field(min_length=1)
    required_cells: frozenset[Cell] = Field(min_length=1)
    notices: tuple[FieldPathError, ...]

    @model_validator(mode="after")
    def complete_constraints(self) -> Self:
        if not self.required_cells <= self.allowed_cells:
            raise ValueError("required cells must be inside the allowed mask")
        validate_immutable(self)
        return self


# GEO-LEGACY-105: Retire the coarse constraints transport with its last strategy caller.
class WaterDesignConstraints(_Constraints[Coord]):
    """Existing coarse strategy transport."""


class FineWaterDesignConstraints(_Constraints[FineXY]):
    """Coastline constraints in the observed native window."""

    coordinate_space: Literal[CoordinateSpace.WORLD_FINE_GRID]
