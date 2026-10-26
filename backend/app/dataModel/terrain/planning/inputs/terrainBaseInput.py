"""Source projection for base terrain planning."""

from typing import Self

from pydantic import BaseModel, ConfigDict, StrictInt, model_validator

from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings


class TerrainBaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    seed: StrictInt
    bbox: GridBBox
    z_min: FineZ
    z_max: FineZ
    grid: SurfaceGridSettings

    @model_validator(mode="after")
    def valid_extent(self) -> Self:
        if self.z_min > self.z_max:
            raise ValueError("z_min exceeds z_max")
        if self.bbox.x_min > self.bbox.x_max or self.bbox.y_min > self.bbox.y_max:
            raise ValueError("terrain bbox requires ordered inclusive bounds")
        return self
