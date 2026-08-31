"""h / L / θ and 45° clamp — C21 / connections §5.1.2.

θ — та же Geom-A, что у grade (relief C3): ``angle_from_height_length``.
No street, threshold, or building ontology here.
"""

from __future__ import annotations

import math
from enum import StrEnum

from app.dataModel.terrain.relief.reliefSlopeGeom import angle_from_height_length

_GRADE_MAX_DEG = 30.0


class ApproachForm(StrEnum):
    NONE = "none"
    GRADE = "grade"
    STAIRS = "stairs"


def approach_angle_deg(h: int, length: int) -> float:
    """Честный θ = atan(h/L) в градусах. Тот же helper, что mill/grade Geom-A.

    ``L < 1`` или ``h = 0`` → 0 (входа-подъёма нет). Иначе делегирует
    ``angle_from_height_length`` (h=1, L=1 → 45°).
    """
    h_i = abs(int(h))
    L = int(length)
    if L < 1 or h_i == 0:
        return 0.0
    return float(angle_from_height_length(h_i, L))


def classify_approach(h: int, length: int) -> tuple[float, ApproachForm]:
    """Bands §5.1.2 on Geom-A θ. Returns ``(theta_rad, form)``.

    Form after assemble is never steeper than STAIRS. θ > 45° still returns
    STAIRS plus ``theta_rad > π/4`` so the caller can clamp.
    """
    deg = approach_angle_deg(h, length)
    if deg <= 0.0:
        return 0.0, ApproachForm.NONE
    theta = math.radians(deg)
    if deg <= _GRADE_MAX_DEG:
        return theta, ApproachForm.GRADE
    return theta, ApproachForm.STAIRS


def clamp_near_z_to_45(z_near: int, z_far: int, length: int) -> int:
    """If ``|z_near - z_far| > L``, move near so ``h = L`` (θ = 45°). Else unchanged."""
    L = int(length)
    near = int(z_near)
    far = int(z_far)
    if L < 1:
        return near
    delta = near - far
    if abs(delta) <= L:
        return near
    sign = 1 if delta > 0 else -1
    return far + sign * L
