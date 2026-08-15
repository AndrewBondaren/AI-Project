"""Shared SideFill profiles — tz_terrain_relief (SLOPE / SHEER)."""

from __future__ import annotations

from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.specs import ReliefSideSpec


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def sheer_band_m(*, sheer_band_light: int, light_m: float) -> float:
    """ε band in meters — SoT: ``sheer_band_light * light_m``."""
    return max(0, int(sheer_band_light)) * max(1.0, float(light_m))


def sheer_fraction_radial(
    *,
    dist_origin: float,
    radius_m: float,
    band_m: float,
) -> float:
    """SHEER: 1 inside outer radius − band, else 0."""
    if dist_origin < float(radius_m) - max(0.0, float(band_m)):
        return 1.0
    return 0.0


def sheer_fraction_lateral(*, dist_spine: float, half_width_m: float, band_m: float) -> float:
    """SHEER on range lateral/cap: 1 until outer edge − band, else 0."""
    half = max(1e-6, float(half_width_m))
    if dist_spine < half - max(0.0, float(band_m)):
        return 1.0
    return 0.0


def slope_fraction(t: float) -> float:
    """SLOPE: smooth falloff ``1 − smoothstep(0,1,t)``."""
    return 1.0 - _smoothstep(0.0, 1.0, max(0.0, min(1.0, t)))


def profile_side_fraction(
    side: ReliefSideSpec,
    *,
    t: float,
    dist_for_sheer: float,
    outer_m: float,
    light_m: float,
) -> float:
    """Apply SHEER/SLOPE profile. ``outer_m`` = radius (peak) or half_width (range)."""
    if side.kind == ReliefSideKind.SHEER:
        band = sheer_band_m(
            sheer_band_light=int(side.sheer_band_light),
            light_m=light_m,
        )
        return sheer_fraction_radial(
            dist_origin=dist_for_sheer,
            radius_m=outer_m,
            band_m=band,
        )
    return slope_fraction(t)
