from app.dataModel.climate.planning.inputs.climateLocalInput import (
    ClimateFeaturePolicy, ProminenceScale as ProminenceScale, ProminenceThresholds as ProminenceThresholds,
)

from dataclasses import dataclass
from typing import Literal
from collections.abc import Mapping

from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.db.models.mapCell import MapCell

TerrainFeatureKind = Literal["peak", "basin", "water"]

# Relative to 8-neighbor ring (meters). Positions only — climate comes from world/coarse field.
MIN_PEAK_PROMINENCE_M = ClimateFeaturePolicy.peak_min
MIN_BASIN_PROMINENCE_M = ClimateFeaturePolicy.basin_min
MIN_LIQUID_PROMINENCE_M = ClimateFeaturePolicy.liquid_min
MAX_AUTO_FEATURES = ClimateFeaturePolicy.max_features


@dataclass(frozen=True)
class TerrainFeaturePoint:
    """Terrain extrema candidate — WHERE to place a Voronoi center, not WHICH climate."""

    gx:       int
    gy:       int
    kind:     TerrainFeatureKind
    prominence: int


def metric_prominence_thresholds() -> ProminenceThresholds:
    """Absolute meter defaults — detailed / fine heightmaps."""
    return ProminenceThresholds(
        peak=MIN_PEAK_PROMINENCE_M,
        basin=MIN_BASIN_PROMINENCE_M,
        liquid=MIN_LIQUID_PROMINENCE_M,
    )


def grid_prominence_thresholds(z_span: int) -> ProminenceThresholds:
    """Scale prominence to heightmap span — coarse / light planning grids."""
    span = max(0, int(z_span))
    return ProminenceThresholds(
        peak=max(1, span // 3),
        basin=max(1, span // 4),
        liquid=max(1, span // 8),
    )


def prominence_thresholds_for_cells(
    cells: list[MapCell],
    *,
    scale: ProminenceScale,
) -> ProminenceThresholds:
    if scale is ProminenceScale.GRID:
        if not cells:
            return ProminenceThresholds(peak=1, basin=1, liquid=1)
        zs = [int(c.z) for c in cells]
        return grid_prominence_thresholds(max(zs) - min(zs))
    return metric_prominence_thresholds()


def prominence_thresholds_for_surface_z(
    surface_z: dict[tuple[int, int], int],
    *,
    scale: ProminenceScale,
) -> ProminenceThresholds:
    if scale is ProminenceScale.GRID:
        if not surface_z:
            return ProminenceThresholds(peak=1, basin=1, liquid=1)
        zs = surface_z.values()
        return grid_prominence_thresholds(max(zs) - min(zs))
    return metric_prominence_thresholds()


def _surface_index(cells: list[MapCell]) -> dict[tuple[int, int], MapCell]:
    by_xy: dict[tuple[int, int], MapCell] = {}
    for cell in cells:
        key = (cell.x, cell.y)
        prev = by_xy.get(key)
        if prev is None or cell.z > prev.z:
            by_xy[key] = cell
    return by_xy


def _neighbors8(gx: int, gy: int) -> list[tuple[int, int]]:
    return [
        (gx + dx, gy + dy)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if dx != 0 or dy != 0
    ]


def detect_terrain_features(
    cells: list[MapCell],
    world_uid: str | None = None,
    *,
    scale: ProminenceScale,
    thresholds: ProminenceThresholds | None = None,
) -> list[TerrainFeaturePoint]:
    """
    Terrain-aware feature points: local extrema relative to neighbors.
    Does not assign climate — N+1 worlds are not Earth.

    ``scale`` is required (METRIC vs GRID). Optional ``thresholds`` overrides derived floors.
    """
    thr = thresholds or prominence_thresholds_for_cells(cells, scale=scale)
    index = _surface_index(cells)
    candidates = terrain_feature_candidates(
        {xy: cell.z for xy, cell in index.items()},
        frozenset(xy for xy, cell in index.items() if cell.system_terrain == "liquid_body"), thr)
    if world_uid and len(candidates) > MAX_AUTO_FEATURES:
        warn_once(world_uid, "auto_features_capped",
                  "climate anchor | world=%s terrain features capped at %d (candidates=%d)",
                  MAX_AUTO_FEATURES, len(candidates))
    return select_terrain_features(candidates, MAX_AUTO_FEATURES)


def terrain_feature_candidates(
    surface_z: Mapping[tuple[int, int], int], water_cells: frozenset[tuple[int, int]],
    thresholds: ProminenceThresholds,
) -> list[tuple[int, TerrainFeaturePoint]]:
    """Shared extrema kernel; insertion order breaks equal-prominence ties."""
    thr = thresholds
    peak_min = int(thr.peak)
    basin_min = int(thr.basin)
    liquid_min = int(thr.liquid)

    candidates: list[tuple[int, TerrainFeaturePoint]] = []

    for (gx, gy), z in surface_z.items():
        neighbor_z = [surface_z[n] for n in _neighbors8(gx, gy) if n in surface_z]
        if not neighbor_z:
            continue

        max_n = max(neighbor_z)
        min_n = min(neighbor_z)

        if z > max_n:
            prominence = z - max_n
            if prominence >= peak_min:
                candidates.append((prominence, TerrainFeaturePoint(
                    gx=gx, gy=gy, kind="peak", prominence=prominence,
                )))

        if z < min_n:
            prominence = min_n - z
            if (gx, gy) in water_cells:
                if prominence >= liquid_min:
                    candidates.append((prominence, TerrainFeaturePoint(
                        gx=gx, gy=gy, kind="water", prominence=prominence,
                    )))
            elif prominence >= basin_min:
                candidates.append((prominence, TerrainFeaturePoint(
                    gx=gx, gy=gy, kind="basin", prominence=prominence,
                )))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def select_terrain_features(candidates: list[tuple[int, TerrainFeaturePoint]],
                            limit: int) -> list[TerrainFeaturePoint]:
    seen: set[tuple[int, int]] = set()
    result: list[TerrainFeaturePoint] = []
    for _, feature in candidates:
        key = (feature.gx, feature.gy)
        if key in seen:
            continue
        seen.add(key)
        result.append(feature)
        if len(result) >= limit:
            break
    return result
