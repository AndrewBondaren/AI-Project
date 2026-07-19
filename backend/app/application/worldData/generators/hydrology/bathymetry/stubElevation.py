"""Open-water surface_z stub — mountain-rise analog (drop from z_sea).

Interim until DepressionForm → Raster → DepthFill. Prefer coarse carved floor when
already ≤ z_sea; else uniform stub drop from ``HydrologySeasPolicy``.
"""

from __future__ import annotations

from app.dataModel.hydrology.seas import HydrologySeasPolicy


def ocean_stub_drop_amount(
    policy: HydrologySeasPolicy,
    *,
    z_sea: int,
    z_min: int,
) -> int:
    """``drop = max(1, round((z_sea - z_min) * stub_drop_fraction_of_span))`` when span > 0."""
    span = max(0, int(z_sea) - int(z_min))
    if span <= 0:
        return 0
    return max(1, int(round(span * float(policy.stub_drop_fraction_of_span))))


def resolve_open_water_surface_z(
    *,
    z_sea: int,
    z_min: int,
    policy: HydrologySeasPolicy,
    coarse_z: int | None = None,
) -> int:
    """
    Bathymetry floor for SEA/LAKE light (or coarse) cell.

    - If ``coarse_z`` already at/below ``z_sea``, use it (post-hydro carve SoT).
    - Else stub: ``z_sea - drop`` clamped to ``z_min`` (depth_fraction=1, no Form yet).
    """
    z_sea_i = int(z_sea)
    z_min_i = int(z_min)
    if coarse_z is not None and int(coarse_z) <= z_sea_i:
        return max(z_min_i, int(coarse_z))
    drop = ocean_stub_drop_amount(policy, z_sea=z_sea_i, z_min=z_min_i)
    return max(z_min_i, z_sea_i - drop)
