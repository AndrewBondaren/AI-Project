from dataclasses import dataclass

from app.application.worldData.generators.climate.climatePoleField import GridBBox


@dataclass(frozen=True)
class SurfaceHeightmap:
    world_uid: str
    bbox:      GridBBox
    surface_z: dict[tuple[int, int], int]


@dataclass(frozen=True)
class ColumnRect:
    x_min: int
    x_max: int
    y_min: int
    y_max: int
