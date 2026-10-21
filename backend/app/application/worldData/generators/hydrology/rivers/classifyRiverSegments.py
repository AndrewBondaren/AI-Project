"""U17/U18 — declare skip; autoresolve classify — D HY-4 / HY-5c."""

from __future__ import annotations
from collections.abc import Sequence

from app.application.worldData.generators.hydrology.geom.polylineRasterize import bresenham_line
from app.dataModel.topology.worldTopology import WorldTopology
from app.application.worldData.generators.hydrology.types import (
    DeclaredRiverEdge,
    RiverSegment,
)
from app.dataModel.hydrology.rivers import RiverTypeClassify
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType


def segments_from_declared(edges: Sequence[DeclaredRiverEdge], *, topology: WorldTopology) -> list[RiverSegment]:
    """U18: bundle edges already typed — no re-classify."""
    if not isinstance(topology, WorldTopology):
        raise TypeError("declared river geometry requires an explicit WorldTopology")
    segments: list[RiverSegment] = []
    for edge in edges:
        cells = bresenham_line(*edge.segment[0], *edge.segment[1])
        cells = list(dict.fromkeys(canonical for cell in cells
                     if (canonical := topology.canonicalize(*cell)) is not None))
        segments.append(RiverSegment(
            polyline_cells=cells,
            connection_type=edge.connection_type,
            edge_uid=edge.edge_uid or None,
            location_uid=edge.location_uid,
            declared=True,
        ))
    return segments


def classify_river_type(
    polyline: list[tuple[int, int]],
    heightmap: SurfaceHeightmap,
    type_classify: RiverTypeClassify,
) -> HydrologyConnectionType:
    """U17: mountain vs lowland from source elevation."""
    # Planner enforces turns in its topology frame. Never drop a bed/drop vertex.
    cells = list(polyline)
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
        return HydrologyConnectionType.MOUNTAIN_RIVER
    else:
        return HydrologyConnectionType.RIVER


def classify_autoresolve_polyline(
    polyline: list[tuple[int, int]],
    heightmap: SurfaceHeightmap,
    type_classify: RiverTypeClassify,
    *, edge_uid: str,
) -> RiverSegment:
    """Attach geometry/identity once; type selection is independent of emission."""
    connection_type = classify_river_type(polyline, heightmap, type_classify)

    return RiverSegment(
        polyline_cells=list(polyline),
        connection_type=connection_type.value,
        edge_uid=edge_uid,
        declared=False,
    )
