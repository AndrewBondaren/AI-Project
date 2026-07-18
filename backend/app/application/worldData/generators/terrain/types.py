from dataclasses import dataclass

from app.application.worldData.generators.climate.climatePoleField import GridBBox


@dataclass(frozen=True)
class SurfaceHeightmap:
    """Coarse/fine surface elevation grid.

    Dataclass is frozen; ``surface_z`` dict is still mutated in place by
    Pass 1.4 (``apply_relief_objects_z``) and hydrology carvers.
    """

    world_uid: str
    bbox:      GridBBox
    surface_z: dict[tuple[int, int], int]


@dataclass(frozen=True)
class ColumnRect:
    x_min: int
    x_max: int
    y_min: int
    y_max: int
