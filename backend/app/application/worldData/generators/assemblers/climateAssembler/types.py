from dataclasses import dataclass
from typing import Literal

from app.application.worldData.generators.coordinates.types import SurfaceGridRect

ClimateChangeKind = Literal["anchor_changed", "zone_changed", "terrain_changed", "manual"]


@dataclass(frozen=True)
class ClimateChangeEvent:
    """
    Input contract for DAG node — **what changed** in master/terrain data.
    Routing (event → passes) lives in the node, not in the generator.
    See tz_climate.md § «Три процесса» / «recalculate_climate».
    """

    kind: ClimateChangeKind
    bbox: SurfaceGridRect | None = None
    location_uids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ClimateRecalcRequest:
    """
    Execution contract for ClimateOrchestratorService.recalculate — **which passes to run**.
    Built by recalculate_climate DAG node from ClimateChangeEvent (+ repos context).
    Generator does not interpret change kind.
    """

    run_pole_resolve: bool = True
    run_anchor_collect: bool = True
    run_cell_weather: bool = True
    output_bbox: SurfaceGridRect | None = None
    include_non_surface: bool = False


# Deprecated name — was incorrectly used as generator input. Use ClimateChangeEvent (node) /
# ClimateRecalcRequest (generator) instead.
RecalcTrigger = ClimateChangeEvent
