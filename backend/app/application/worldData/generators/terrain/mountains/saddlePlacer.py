"""SaddlePlacer — MST edges → MountainSaddleSpec (tz_mountain_architecture U3).

``MountainSaddleSpec.peak_a_index`` / ``peak_b_index`` are indices into
``MountainRangeSpec.peaks[]`` (contiguous 0..n-1), **not** ``RidgeVertex.index``.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.ridgeGraph.types import RidgeGraph
from app.dataModel.terrainMasks.mountain.enums import mountain_kind_profile
from app.dataModel.terrainMasks.mountain.specs import MountainSaddleSpec, MountainSpec


def resolve_saddle_rise_fraction(
    *,
    saddle: MountainSaddleSpec | None,
    range_fraction: float | None,
    peak_a: MountainSpec,
    peak_b: MountainSpec,
) -> float:
    """Priority: SaddleSpec → Range → KindProfile (POJO default 0.65)."""
    if saddle is not None and saddle.rise_fraction is not None:
        return float(saddle.rise_fraction)
    if range_fraction is not None:
        return float(range_fraction)
    fa = float(mountain_kind_profile(peak_a.kind).saddle_rise_fraction)
    fb = float(mountain_kind_profile(peak_b.kind).saddle_rise_fraction)
    return min(fa, fb)


def validate_saddle_peak_indices(saddle: MountainSaddleSpec, n_peaks: int) -> None:
    """Raise if indices are not distinct members of ``Range.peaks[]``."""
    a = int(saddle.peak_a_index)
    b = int(saddle.peak_b_index)
    if a == b:
        raise ValueError(
            f"MountainSaddleSpec peak_a_index == peak_b_index == {a} "
            "(must reference two distinct Range.peaks[] entries)"
        )
    if not (0 <= a < n_peaks and 0 <= b < n_peaks):
        raise ValueError(
            f"MountainSaddleSpec indices ({a},{b}) out of range for "
            f"Range.peaks length {n_peaks} (indices are Range.peaks[], "
            "not RidgeVertex.index)"
        )


def place_saddles_on_mst(
    graph: RidgeGraph,
    peaks_by_index: dict[int, MountainSpec],
    *,
    peak_index_in_range: dict[int, int],
    range_saddle_rise_fraction: float | None = None,
    declared: list[MountainSaddleSpec] | None = None,
    n_peaks: int | None = None,
) -> list[MountainSaddleSpec]:
    """Empty declared → one saddle per MST edge; else validate + keep declared.

    Indices written here are ``Range.peaks[]`` positions via ``peak_index_in_range``.
    """
    n = n_peaks if n_peaks is not None else len(peak_index_in_range)
    if declared:
        for s in declared:
            validate_saddle_peak_indices(s, n)
        return list(declared)
    out: list[MountainSaddleSpec] = []
    for e in graph.edges:
        ia = peak_index_in_range[e.a]
        ib = peak_index_in_range[e.b]
        peak_a = peaks_by_index[e.a]
        peak_b = peaks_by_index[e.b]
        f = resolve_saddle_rise_fraction(
            saddle=None,
            range_fraction=range_saddle_rise_fraction,
            peak_a=peak_a,
            peak_b=peak_b,
        )
        saddle = MountainSaddleSpec(
            peak_a_index=min(ia, ib),
            peak_b_index=max(ia, ib),
            rise_fraction=f,
        )
        validate_saddle_peak_indices(saddle, n)
        out.append(saddle)
    return out
