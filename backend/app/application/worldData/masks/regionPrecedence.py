"""Cell coverage precedence — tz_map_light_bake § Пересечения и приоритет."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.terrainMasks.regions import RegionSpecBase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegionCandidate:
    """Resolved cell contender: current terrain may differ from declaration type."""

    current_type: TerrainKey
    spec: RegionSpecBase
    region_uid: str


def _precedence_key(candidate: RegionCandidate, rank: int) -> tuple[int, bool, int, float, str]:
    specificity = candidate.spec.placement_specificity
    return (
        -rank,
        specificity is None,
        -(specificity or 0),
        -candidate.spec.shape.area(),
        candidate.region_uid,
    )


def compare_region_candidates(
    left: RegionCandidate,
    right: RegionCandidate,
    *,
    merge_rank: Callable[[TerrainKey], int],
) -> int:
    """Negative: left wins; positive: right wins; zero: equal precedence.

    Rank is supplied by the caller: today ``terrain_merge_rank`` bound to
    ``WorldTerrainMasks``, after cutover a registry-entry lookup. No world
    reads, geometry changes, or error defaults occur here. The only side
    effect is the required diagnostic for equal-rank, different-key outcomes.
    """
    left_rank = merge_rank(left.current_type)
    right_rank = merge_rank(right.current_type)
    left_key = _precedence_key(left, left_rank)
    right_key = _precedence_key(right, right_rank)
    result = (left_key > right_key) - (left_key < right_key)
    if left_rank == right_rank and left.current_type != right.current_type and result:
        winner, loser = (left, right) if result < 0 else (right, left)
        logger.warning(
            "landcover | equal_rank_resolved | WarningError | merge_rank=%s "
            "winner_uid=%s winner_type=%s loser_uid=%s loser_type=%s",
            left_rank, winner.region_uid, winner.current_type, loser.region_uid, loser.current_type,
        )
    return result
