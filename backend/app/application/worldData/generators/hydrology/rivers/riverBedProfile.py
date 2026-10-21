"""River profile emission and post-relief roles (HY-12/5)."""

from collections.abc import Mapping

from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.hydrology.waterBodyIdentity import AutoWaterBodyRole, water_body_uid_for
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.topology.worldTopology import Coord


def river_bed_spec(heightmap: SurfaceHeightmap, segment: RiverSegment, *, depth_step: int,
                   z_min: int, occupied: Mapping[Coord, MapCellHydrology]) -> RiverBedSpec:
    """Read pre-bed elevations; stop at first receiving water and keep its floor."""
    bed = []
    for cell in segment.polyline_cells:
        if cell not in heightmap.surface_z:
            continue
        if is_river_mouth(cell, heightmap.surface_z, occupied):
            break
        z = heightmap.surface_z[cell]
        lowered_z = max(z_min, z - depth_step)
        # Carve must not lift an existing floor that is already below z_min.
        bed.append((cell, min(z, lowered_z)))
    return RiverBedSpec(tuple(bed))


def river_bed_roles(segment: RiverSegment, spec: RiverBedSpec, *,
                    drainage: RiverDrainageLink | None = None) -> dict[Coord, MapCellHydrology]:
    if not segment.polyline_cells:
        return {}
    uid = drainage.river_uid if drainage else water_body_uid_for(
        segment.location_uid, AutoWaterBodyRole.RIVER, segment.polyline_cells[0])
    return {cell: MapCellHydrology(role=HydrologyCellRole.RIVER_BED,
                                  connection_edge_uid=segment.edge_uid, water_body_uid=uid,
                                  river_drainage=drainage)
            for cell, _ in spec.bed_z}
