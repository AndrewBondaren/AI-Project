"""Keep river vertical steps, including the drop onto a receiving waterline."""

from collections.abc import Mapping

from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.waterfallDrop import WaterfallDrop
from app.dataModel.topology.worldTopology import Coord


def river_drop_facts(heightmap: SurfaceHeightmap, segment: RiverSegment, spec: RiverBedSpec,
                     occupied: Mapping[Coord, MapCellHydrology]) -> tuple[WaterfallDrop, ...]:
    profile = dict(spec.bed_z)
    for cell in segment.polyline_cells:
        entry = occupied.get(cell)
        if cell == segment.polyline_cells[-1] and entry is not None and (
                entry.role is HydrologyCellRole.RIVER_BED and entry.river_drainage is not None):
            profile[cell] = heightmap.surface_z[cell]
            break
        if is_river_mouth(cell, heightmap.surface_z, occupied):
            entry = occupied[cell]
            profile[cell] = entry.z_water_level if entry.z_water_level is not None else heightmap.surface_z[cell]
            break
    return tuple(WaterfallDrop(upper_cell=upper, lower_cell=lower,
                               upper_z=profile[upper], lower_z=profile[lower],
                               connection_edge_uid=segment.edge_uid)
                 for upper, lower in zip(segment.polyline_cells, segment.polyline_cells[1:])
                 if upper in profile and lower in profile and profile[upper] > profile[lower])
