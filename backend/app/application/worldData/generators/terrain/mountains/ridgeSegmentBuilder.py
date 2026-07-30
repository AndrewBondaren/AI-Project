"""RidgeSegmentBuilder — context → MountainRangeSpec (tz_mountain_architecture).

TODO(U4): full ``context → params`` mapping — docs/tz_mountain_architecture.md U4.
v1 secondary stub: 0.5 × primary radius_m / width_m.

Saddle indices on the built Range are ``Range.peaks[]`` positions (0..n-1),
remapped from ``RidgeVertex.index`` via ``peak_index_in_range``.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.ridgeGraph.types import (
    RidgeGraph,
    RidgeSegmentContext,
)
from app.application.worldData.generators.terrain.mountains.saddlePlacer import place_saddles_on_mst
from app.application.worldData.generators.terrain.mountains.spineSampler import sample_spine
from app.dataModel.terrainMasks.mountain.enums import MountainRangeStyle
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy

# TODO(U4): replace fixed scale with full context→params (tz_mountain_architecture U4).
_SECONDARY_SCALE = 0.5


def build_primary_range(
    graph: RidgeGraph,
    *,
    policy: MountainsCategoryPolicy,
    style: MountainRangeStyle | None = None,
    peak_gap_m: float,
) -> MountainRangeSpec:
    peaks = [v.peak for v in graph.vertices]
    peaks_by_index = {v.index: v.peak for v in graph.vertices}
    # Contiguous peak indices inside Range.peaks[] (SoT for MountainSaddleSpec).
    peak_index_in_range = {v.index: i for i, v in enumerate(graph.vertices)}
    range_style = style or policy.default_range_style
    spine = sample_spine(
        graph,
        range_style,
        peak_gap_m=peak_gap_m,
        hybrid_smooth_edge_factor=float(policy.hybrid_smooth_edge_factor),
    )
    width = max(1, int(policy.default_radius_m))
    kind = peaks[0].kind if peaks else policy.default_kind
    saddles = place_saddles_on_mst(
        graph,
        peaks_by_index,
        peak_index_in_range=peak_index_in_range,
        n_peaks=len(peaks),
    )
    return MountainRangeSpec(
        spine=spine,
        width_m=width,
        kind=kind,
        peaks=peaks,
        style=range_style,
        saddles=saddles,
        peak_spacing_m=max(1, int(round(peak_gap_m))),
    )


def build_secondary_ranges(
    primary: MountainRangeSpec,
    *,
    policy: MountainsCategoryPolicy,
    contexts: list[RidgeSegmentContext] | None = None,
) -> list[MountainRangeSpec]:
    """Secondary stub: one spur scaled 0.5× from primary endpoints.

    TODO(U4): full context→params — docs/tz_mountain_architecture.md U4.
    """
    if not policy.enable_secondary_ridges:
        return []
    ctxs = contexts or [RidgeSegmentContext.SPUR_FROM_PEAK]
    if not primary.peaks or len(primary.spine) < 2:
        return []
    out: list[MountainRangeSpec] = []
    # Stub: short spur from first peak along first spine segment.
    p0 = primary.spine[0]
    p1 = primary.spine[1]
    mid = (
        int(round(p0[0] + (p1[0] - p0[0]) * _SECONDARY_SCALE)),
        int(round(p0[1] + (p1[1] - p0[1]) * _SECONDARY_SCALE)),
    )
    for ctx in ctxs:
        if ctx == RidgeSegmentContext.PRIMARY_MST_EDGE:
            continue
        width = max(1, int(round(primary.width_m * _SECONDARY_SCALE)))
        peaks: list[MountainSpec] = []
        if primary.peaks:
            src = primary.peaks[0]
            peaks.append(
                MountainSpec(
                    origin_x_m=p0[0],
                    origin_y_m=p0[1],
                    radius_m=max(1, int(round(src.radius_m * _SECONDARY_SCALE))),
                    kind=src.kind,
                    form=src.form,
                    sides=list(src.sides) if src.sides else [],
                )
            )
        out.append(
            MountainRangeSpec(
                spine=[p0, mid],
                width_m=width,
                kind=primary.kind,
                peaks=peaks,
                style=policy.default_range_style,
                saddles=[],
            )
        )
    return out
