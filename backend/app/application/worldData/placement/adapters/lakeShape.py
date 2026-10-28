"""Declared lake shoreline → pre-carve interior and rim level; no carve."""

from pydantic import ValidationError

from app.application.worldData.placement.adapters.coastlineShape import (
    cell_neighbors, ring_barrier, ring_sides,
)
from app.application.worldData.placement.adapters.waterTypes import (
    WaterGeometryError, WaterGeometryView,
)
from app.dataModel.identity.uid import EntityUid
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.spatial.regionShape import PolygonShape
from app.dataModel.topology.worldTopology import Coord


def lake_cells(lake: DeclaredLake, context: WaterGeometryView, *, seed_root: EntityUid) -> tuple[frozenset[Coord], bool]:
    points = [(p.x, p.y) for p in lake.shoreline]
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(set(points)) < 2:
        raise WaterGeometryError("lake shoreline requires at least two distinct waypoints")
    segments = [*zip(points, points[1:]), (points[-1], points[0])]
    barrier = ring_barrier(context, segments)
    try:
        polygon = PolygonShape(vertices=tuple(points))
    except ValidationError:
        return frozenset(barrier), True
    inside, _ = ring_sides(polygon, lake.location_uid, context, barrier, seed_root=seed_root)
    if not inside:
        return frozenset(barrier), True
    return frozenset(inside), False


def lake_level(cells: frozenset[Coord], context: WaterGeometryView) -> int:
    """Legacy rim: highest pre-carve land cell touching the water footprint."""
    rim = [context.surface_z[n] for cell in cells for n in cell_neighbors(context.topology, cell) if n not in cells]
    return max(rim, default=max(context.surface_z[cell] for cell in cells))
