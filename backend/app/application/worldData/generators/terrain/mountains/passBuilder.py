"""MountainPassBuilder — topology facade (tz_mountain_architecture).

candidates → PeakAssembler → SummitAnchor → SystemCluster →
  Graph / Saddle / Spine / RidgeSegmentBuilder → secondary stub → RangeGapFilter.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.peakAssembler import (
    assemble_peaks_from_candidates,
)
from app.application.worldData.generators.terrain.mountains.rangeGapFilter import (
    filter_auto_by_range_gap,
)
from app.application.worldData.generators.terrain.mountains.ridgeGraphBuilder import (
    build_mst_graph,
)
from app.application.worldData.generators.terrain.mountains.ridgePlacement import RidgeCandidate
from app.application.worldData.generators.terrain.mountains.ridgeSegmentBuilder import (
    build_primary_range,
    build_secondary_ranges,
)
from app.application.worldData.generators.terrain.mountains.systemCluster import (
    cluster_systems,
    vertices_from_peaks,
)
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy

MountainEntry = MountainSpec | MountainRangeSpec


class MountainPassBuilder:
    """Build auto mountain Specs/Ranges from ridge candidates (topology only)."""

    def build(
        self,
        candidates: list[RidgeCandidate],
        policy: MountainsCategoryPolicy,
        *,
        seed: int,
        reserved: list[MountainEntry] | None = None,
    ) -> list[MountainEntry]:
        if not policy.autoresolve or not candidates:
            return []
        peaks = assemble_peaks_from_candidates(candidates, policy)
        vertices = vertices_from_peaks(peaks)
        systems = cluster_systems(vertices)
        auto: list[MountainEntry] = []
        for system in systems:
            if len(system.vertices) < 2:
                auto.append(system.vertices[0].peak)
                continue
            graph = build_mst_graph(list(system.vertices))
            primary = build_primary_range(
                graph,
                policy=policy,
                peak_gap_m=system.peak_gap_m,
            )
            auto.append(primary)
            auto.extend(build_secondary_ranges(primary, policy=policy))
        return filter_auto_by_range_gap(
            auto,
            list(reserved or []),
            policy,
            seed=seed,
        )


def build_mountain_pass(
    candidates: list[RidgeCandidate],
    policy: MountainsCategoryPolicy,
    *,
    seed: int,
    reserved: list[MountainEntry] | None = None,
) -> list[MountainEntry]:
    return MountainPassBuilder().build(
        candidates, policy, seed=seed, reserved=reserved,
    )
