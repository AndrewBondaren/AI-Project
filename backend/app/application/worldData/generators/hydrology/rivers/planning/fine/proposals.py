"""Convert accepted coarse proposals into fine requests, without source discovery."""
from dataclasses import replace

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.coordinates.light.grid import light_cell_center_fine
from app.application.worldData.generators.hydrology.geom.polylineRasterize import bresenham_line
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import (
    RiverRouteRequest, request_from_prepared_segments,
)
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.topology.topologyGeometry import unrolled_images
from app.dataModel.topology.worldTopology import Coord, WorldTopology


def _path(cells: tuple[SurfaceGridCoord, ...], scale: LightGridScale, topology: WorldTopology,
          control: PlanBuildControl) -> list[Coord]:
    points: list[Coord] = []
    for cell in cells:
        control.raise_if_shutdown()
        target = light_cell_center_fine(cell.gx, cell.gy, 0, 0, scale)
        if not points:
            points.append(target)
            continue
        start = points[-1]
        x, y = unrolled_images(topology, target, anchor=start)[0].coord
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError("coarse proposal refinement requires integer topology images")
        leg = [canonical for point in bresenham_line(*start, x, y)
               if (canonical := topology.canonicalize(*point)) is not None]
        points.extend(leg[1:])
    return points


def procedural_requests(proposals: tuple[RiverRoute[SurfaceGridCoord], ...], *, span: int,
                        heightmap: SurfaceHeightmap, occupied: dict[Coord, MapCellHydrology],
                        topology: WorldTopology, control: PlanBuildControl) -> tuple[RiverRouteRequest, ...]:
    scale = LightGridScale.from_tile(span, 1)
    requests = []
    for route in proposals:
        control.raise_if_shutdown()
        segments = tuple(RiverSegment(polyline_cells=_path(segment.path, scale, topology, control),
            connection_type=segment.connection_type.value, edge_uid=segment.edge_uid,
            location_uid=segment.location_uid, declared=segment.declared) for segment in route.segments)
        request = request_from_prepared_segments(1, segments, occupied, heightmap.surface_z,
                                                 space=CoordinateSpace.WORLD_FINE_GRID)
        requests.append(replace(request, object_uid=route.river_uid,
                                requested_receiver_uid=route.drainage.receiver_uid))
    return tuple(requests)
