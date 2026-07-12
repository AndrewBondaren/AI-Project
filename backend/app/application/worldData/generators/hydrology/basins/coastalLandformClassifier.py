"""Read-only coastal landform tags — D HY-2 scope LANDFORMS."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.types import HydrologyMasterInput


@dataclass(frozen=True)
class CoastalLandforms:
    islands: list[tuple[int, int]] = field(default_factory=list)
    peninsulas: list[tuple[int, int]] = field(default_factory=list)
    coastline_polylines: list[list[tuple[int, int]]] = field(default_factory=list)


def classify_coastal_landforms(master: HydrologyMasterInput) -> CoastalLandforms:
    """v1: expose declare coastline polylines only (no heightmap mutation)."""
    segments = master.declared_coastline_segments
    cells = sorted(rasterize_segments(segments))
    polylines = [cells] if cells else []
    return CoastalLandforms(coastline_polylines=polylines)
