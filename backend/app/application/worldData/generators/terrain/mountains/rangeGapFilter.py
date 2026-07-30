"""RangeGapFilter — drop conflicting auto ranges (tz_mountain_architecture U1)."""

from __future__ import annotations

import math
import random

from app.dataModel.terrainMasks.mountain.enums import mountain_kind_profile
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy

MountainEntry = MountainSpec | MountainRangeSpec


def _spine_length_m(spine: list[tuple[int, int]]) -> float:
    total = 0.0
    for i in range(len(spine) - 1):
        ax, ay = spine[i]
        bx, by = spine[i + 1]
        total += math.hypot(bx - ax, by - ay)
    return total


def _centroid(spine: list[tuple[int, int]]) -> tuple[float, float]:
    if not spine:
        return 0.0, 0.0
    sx = sum(p[0] for p in spine) / len(spine)
    sy = sum(p[1] for p in spine) / len(spine)
    return sx, sy


def range_gap_bounds_m(
    spec: MountainRangeSpec,
    policy: MountainsCategoryPolicy,
) -> tuple[float, float]:
    l_m = _spine_length_m(list(spec.spine))
    r = float(spec.width_m)
    h_rel = float(mountain_kind_profile(spec.kind).rise_fraction_of_z_max)
    gap_min = max(
        2.0 * r,
        float(policy.range_gap_length_fraction) * l_m
        + (1.0 + float(policy.range_gap_height_factor) * h_rel) * r,
    )
    gap_max = gap_min * float(policy.range_gap_spread)
    return gap_min, gap_max


def _spec_footprint_center(entry: MountainEntry) -> tuple[float, float]:
    if isinstance(entry, MountainRangeSpec):
        return _centroid(list(entry.spine))
    return float(entry.origin_x_m), float(entry.origin_y_m)


def _spec_radius_m(entry: MountainEntry) -> float:
    if isinstance(entry, MountainRangeSpec):
        return float(entry.width_m)
    return float(entry.radius_m)


def conflict_need_m(
    entry: MountainEntry,
    other: MountainEntry,
    policy: MountainsCategoryPolicy,
    rng: random.Random,
) -> float:
    """Single conflict-distance table for Spec↔Range / Range↔Range."""
    if isinstance(entry, MountainRangeSpec):
        gap_min, gap_max = range_gap_bounds_m(entry, policy)
        need = rng.uniform(gap_min, gap_max)
        return need + _spec_radius_m(other) * float(policy.range_gap_other_radius_factor)
    # Peak vs other
    if isinstance(other, MountainRangeSpec):
        gap_min, gap_max = range_gap_bounds_m(other, policy)
        return rng.uniform(gap_min, gap_max)
    return _spec_radius_m(entry) + _spec_radius_m(other)


def filter_auto_by_range_gap(
    auto: list[MountainEntry],
    reserved: list[MountainEntry],
    policy: MountainsCategoryPolicy,
    *,
    seed: int,
) -> list[MountainEntry]:
    """Drop auto entries that fall inside gap vs reserved+kept auto. Declare untouched."""
    rng = random.Random(seed)
    kept: list[MountainEntry] = []
    obstacles = list(reserved)
    for entry in auto:
        cx, cy = _spec_footprint_center(entry)
        conflict = False
        for other in obstacles:
            ox, oy = _spec_footprint_center(other)
            need = conflict_need_m(entry, other, policy, rng)
            if math.hypot(cx - ox, cy - oy) < need:
                conflict = True
                break
        if conflict:
            continue
        kept.append(entry)
        obstacles.append(entry)
    return kept
