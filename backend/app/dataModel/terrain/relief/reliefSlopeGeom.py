"""Cubic-cell SLOPE triangle formulas — tz_terrain_relief R36c–d.

One cell: ``cell_xy_m == cell_z_m``. Bake uses Geom-A and Geom-B; Geom-C is
UI-only (R30) and must not override map height.
"""

from __future__ import annotations

import math


def angle_from_height_length(h: int, length: int) -> float:
    """Geom-A: ``θ = atan(h / L)`` in degrees (h=1, L=1 → 45)."""
    h_i = max(0, int(h))
    L = max(1, int(length))
    if h_i < 1:
        return 0.0
    return math.degrees(math.atan(h_i / L))


def length_from_target_angle(h: int, angle_deg: float) -> int:
    """Geom-B: ``L = ceil(h / tan θ)``, minimum 1."""
    h_i = max(0, int(h))
    if h_i < 1:
        return 1
    theta = float(angle_deg)
    if theta <= 0.0 or theta >= 90.0:
        raise ValueError(f"target_angle_deg must be in (0, 90); got {theta}")
    tan_t = math.tan(math.radians(theta))
    if tan_t <= 0.0:
        raise ValueError(f"tan(target_angle_deg) must be > 0; got θ={theta}")
    return max(1, math.ceil(h_i / tan_t))


def height_from_length_angle(length: int, angle_deg: float) -> float:
    """Geom-C: ``h = L · tan θ``. UI calculator only — not a bake override."""
    L = max(0, int(length))
    theta = float(angle_deg)
    if theta <= 0.0 or theta >= 90.0:
        raise ValueError(f"target_angle_deg must be in (0, 90); got {theta}")
    return L * math.tan(math.radians(theta))
