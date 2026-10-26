"""River profile emission and post-relief roles (HY-12/5)."""

from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.hydrology.waterBodyIdentity import AutoWaterBodyRole, water_body_uid_for
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedZ import river_bed_spec as river_bed_spec
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.topology.worldTopology import Coord


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
