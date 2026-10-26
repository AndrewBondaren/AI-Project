"""Complete immutable terrain surface; consumers allocate their own working buffers."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox


class TerrainPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    bbox: GridBBox
    surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...]

    @model_validator(mode="after")
    def complete_surface(self) -> Self:
        box = self.bbox
        if box.x_min > box.x_max or box.y_min > box.y_max:
            raise ValueError("terrain bbox requires ordered inclusive bounds")
        coords = tuple(coord for coord, _ in self.surface_z)
        if len(set(coords)) != len(coords):
            raise ValueError("duplicate terrain surface coordinate")
        if any(not (box.x_min <= coord.gx <= box.x_max and box.y_min <= coord.gy <= box.y_max)
               for coord in coords):
            raise ValueError("terrain surface coordinate outside bbox")
        if len(coords) != (box.x_max - box.x_min + 1) * (box.y_max - box.y_min + 1):
            raise ValueError("terrain surface must cover the inclusive bbox")
        if coords != tuple(sorted(coords, key=lambda coord: (coord.gy, coord.gx))):
            raise ValueError("terrain surface must be in row-major order")
        return self
