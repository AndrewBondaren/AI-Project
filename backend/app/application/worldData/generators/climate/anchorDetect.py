from dataclasses import dataclass
from typing import Literal

from app.db.models.mapCell import MapCell

TerrainFeatureKind = Literal["peak", "basin", "water"]

# Relative to 8-neighbor ring (meters). Positions only — climate comes from world/coarse field.
MIN_PEAK_PROMINENCE_M = 50
MIN_BASIN_PROMINENCE_M = 25
MIN_LIQUID_PROMINENCE_M = 10
MAX_AUTO_FEATURES = 32


@dataclass(frozen=True)
class TerrainFeaturePoint:
    """Terrain extrema candidate — WHERE to place a Voronoi center, not WHICH climate."""

    gx:       int
    gy:       int
    kind:     TerrainFeatureKind
    prominence: int


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


def detect_terrain_features(cells: list[MapCell]) -> list[TerrainFeaturePoint]:
    """
    Terrain-aware feature points: local extrema relative to neighbors.
    Does not assign climate — N+1 worlds are not Earth.
    """
    if not cells:
        return []

    index = _surface_index(cells)
    candidates: list[tuple[int, TerrainFeaturePoint]] = []

    for (gx, gy), cell in index.items():
        neighbor_z = [index[n].z for n in _neighbors8(gx, gy) if n in index]
        if not neighbor_z:
            continue

        max_n = max(neighbor_z)
        min_n = min(neighbor_z)

        if cell.z > max_n:
            prominence = cell.z - max_n
            if prominence >= MIN_PEAK_PROMINENCE_M:
                candidates.append((prominence, TerrainFeaturePoint(
                    gx=gx, gy=gy, kind="peak", prominence=prominence,
                )))

        if cell.z < min_n:
            prominence = min_n - cell.z
            if cell.system_terrain == "liquid_body":
                if prominence >= MIN_LIQUID_PROMINENCE_M:
                    candidates.append((prominence, TerrainFeaturePoint(
                        gx=gx, gy=gy, kind="water", prominence=prominence,
                    )))
            elif prominence >= MIN_BASIN_PROMINENCE_M:
                candidates.append((prominence, TerrainFeaturePoint(
                    gx=gx, gy=gy, kind="basin", prominence=prominence,
                )))

    candidates.sort(key=lambda item: item[0], reverse=True)
    seen: set[tuple[int, int]] = set()
    result: list[TerrainFeaturePoint] = []
    for _, feature in candidates:
        key = (feature.gx, feature.gy)
        if key in seen:
            continue
        seen.add(key)
        result.append(feature)
        if len(result) >= MAX_AUTO_FEATURES:
            break
    return result
