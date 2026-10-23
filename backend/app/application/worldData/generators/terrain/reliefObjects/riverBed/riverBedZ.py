"""Relief owns river elevation writes; replaying an absolute spec is idempotent."""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from .riverBedSpec import RiverBedSpec
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.topology.worldTopology import Coord

if TYPE_CHECKING:
    from app.application.worldData.generators.hydrology.types import RiverSegment


def river_bed_spec(heightmap: SurfaceHeightmap, segment: "RiverSegment", *, depth_step: int,
                   z_min: int, occupied: Mapping[Coord, MapCellHydrology],
                   receiver_cell: Coord | None = None) -> RiverBedSpec:
    """Read pre-bed elevations; preserve the accepted receiver and existing water floors."""
    bed = []
    for cell in segment.polyline_cells:
        if cell not in heightmap.surface_z:
            continue
        if cell == receiver_cell or is_river_mouth(cell, heightmap.surface_z, occupied):
            break
        z = heightmap.surface_z[cell]
        bed.append((cell, min(z, max(z_min, z - depth_step))))
    return RiverBedSpec(tuple(bed))


def apply_river_bed_z(heightmap: SurfaceHeightmap, specs: Sequence[RiverBedSpec]) -> None:
    targets = {}
    for spec in specs:
        for cell, z in spec.bed_z:
            if cell in heightmap.surface_z:
                targets[cell] = min(targets.get(cell, z), z)
    heightmap.surface_z.update(targets)
