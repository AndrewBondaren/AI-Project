"""Piecewise basin floor profile by boundary distance (HY-12 step 3a)."""

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKindProfile


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def floor_profile_z(d: int, *, level: int, floor_z: int, bands: HydrologyBands,
                    profile: BasinKindProfile) -> int:
    top = level - 1
    depth = top - floor_z
    assert depth >= 0, "floor_z must be below z_water_level"
    d_shelf, d_slope = bands.min, bands.max
    fraction = profile.shelf_depth_fraction
    if fraction is None:
        z = floor_z + round(depth * (1 - min(d, d_slope) / d_slope))
    else:
        z_shelf = top - round(depth * fraction)
        if d <= d_shelf:
            z = _lerp(top, z_shelf, d / d_shelf)
        elif d <= d_slope:
            z = floor_z if d_slope == d_shelf else _lerp(
                z_shelf, floor_z, (d - d_shelf) / (d_slope - d_shelf))
        else:
            z = floor_z
    return min(top, max(floor_z, z))
