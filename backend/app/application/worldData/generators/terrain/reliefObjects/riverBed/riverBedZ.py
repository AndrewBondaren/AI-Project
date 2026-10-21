"""Relief owns river elevation writes; replaying an absolute spec is idempotent."""

from collections.abc import Sequence

from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from .riverBedSpec import RiverBedSpec


def apply_river_bed_z(heightmap: SurfaceHeightmap, specs: Sequence[RiverBedSpec]) -> None:
    targets = {}
    for spec in specs:
        for cell, z in spec.bed_z:
            if cell in heightmap.surface_z:
                targets[cell] = min(targets.get(cell, z), z)
    heightmap.surface_z.update(targets)
