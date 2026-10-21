"""River profile emission and post-relief roles (HY-12/5)."""

from collections.abc import Mapping

from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.types import RiverSegment, RiverTypeClassify
from app.application.worldData.generators.hydrology.waterBodyIdentity import AutoWaterBodyRole, water_body_uid_for
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.topology.worldTopology import Coord


def _channel_depth_step(connection_type: str, type_classify: RiverTypeClassify) -> int:
    base = 1
    if HydrologyConnectionType.from_wire(connection_type) == HydrologyConnectionType.MOUNTAIN_RIVER:
        return max(1, int(round(base * type_classify.mountain_bed_steepness_factor)))
    return base


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
        bed.append((cell, min(z, max(z_min, z - depth_step))))
    return RiverBedSpec(tuple(bed))


def river_bed_roles(segment: RiverSegment, spec: RiverBedSpec) -> dict[Coord, MapCellHydrology]:
    if not segment.polyline_cells:
        return {}
    uid = water_body_uid_for(segment.location_uid, AutoWaterBodyRole.RIVER, segment.polyline_cells[0])
    return {cell: MapCellHydrology(role=HydrologyCellRole.RIVER_BED,
                                  connection_edge_uid=segment.edge_uid, water_body_uid=uid)
            for cell, _ in spec.bed_z}
