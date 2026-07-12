"""U17/U18 — declare skip; autoresolve classify — D HY-4 / HY-5c."""

from __future__ import annotations

from app.application.worldData.generators.hydrology.geom.polylineRasterize import bresenham_line
from app.application.worldData.generators.hydrology.geom.smoothRiverPolyline import smooth_polyline_cells
from app.application.worldData.generators.hydrology.types import (
    DeclaredRiverEdge,
    RiverSegment,
    RiverTypeClassify,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType


def segments_from_declared(edges: list[DeclaredRiverEdge]) -> list[RiverSegment]:
    """U18: bundle edges already typed — no re-classify."""
    segments: list[RiverSegment] = []
    for edge in edges:
        cells = bresenham_line(*edge.segment[0], *edge.segment[1])
        segments.append(RiverSegment(
            polyline_cells=cells,
            connection_type=edge.connection_type,
            edge_uid=edge.edge_uid or None,
            location_uid=edge.location_uid,
            declared=True,
        ))
    return segments


def classify_autoresolve_polyline(
    polyline: list[tuple[int, int]],
    heightmap: SurfaceHeightmap,
    type_classify: RiverTypeClassify,
    *,
    edge_uid: str,
) -> RiverSegment:
    """U17: mountain vs lowland from source elevation."""
    cells = smooth_polyline_cells(polyline)
    source_z = heightmap.surface_z.get(cells[0], 0)
    mountain_fraction = 0.0
    if len(cells) > 1:
        high_steps = sum(
            1
            for cell in cells
            if heightmap.surface_z.get(cell, 0) >= type_classify.mountain_min_source_z
        )
        mountain_fraction = high_steps / len(cells)

    if (
        source_z >= type_classify.mountain_min_source_z
        or mountain_fraction >= type_classify.path_mountain_fraction
    ):
        connection_type = HydrologyConnectionType.MOUNTAIN_RIVER.value
    else:
        connection_type = HydrologyConnectionType.RIVER.value

    return RiverSegment(
        polyline_cells=cells,
        connection_type=connection_type,
        edge_uid=edge_uid,
        declared=False,
    )
