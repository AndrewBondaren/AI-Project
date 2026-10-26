"""Accepted open-water facts passed between hydrology stage owners."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.planning.hydrologyPlan import coarse_order, require_map, require_unique_water
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord


class OpenWaterPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    coarse_open_water: tuple[tuple[SurfaceGridCoord, MapCellHydrology], ...]
    water_bodies: tuple[WaterBody, ...]
    physical_unions: tuple[PhysicalWaterUnion, ...]

    @model_validator(mode="after")
    def consistent_water(self) -> Self:
        require_map(self.coarse_open_water, coarse_order)
        require_unique_water(self.water_bodies, self.physical_unions)
        return self
