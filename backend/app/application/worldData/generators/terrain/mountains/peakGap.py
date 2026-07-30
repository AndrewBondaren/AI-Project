"""Peak gap resolution — tz_mountain_architecture peak spacing priority."""

from __future__ import annotations

from app.dataModel.terrainMasks.mountain.enums import MountainKind, mountain_kind_profile
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec


def resolve_peak_gap_m(
    *,
    kind: MountainKind,
    radius_m: float,
    range_spec: MountainRangeSpec | None = None,
) -> float:
    """Priority: ``peak_spacings_m`` → ``peak_spacing_m`` → auto ``R*(1-inset)``."""
    if range_spec is not None:
        if range_spec.peak_spacings_m:
            return max(1.0, float(min(int(s) for s in range_spec.peak_spacings_m)))
        if range_spec.peak_spacing_m is not None:
            return max(1.0, float(range_spec.peak_spacing_m))
    profile = mountain_kind_profile(kind)
    inset = float(profile.peak_gap_inset_fraction)
    return max(1.0, float(radius_m) * (1.0 - inset))


def peak_gap_m_for_spec(spec: MountainSpec) -> float:
    return resolve_peak_gap_m(kind=spec.kind, radius_m=float(spec.radius_m))
