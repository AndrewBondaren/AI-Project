"""Range U6 compose — corridor → saddle modulate (tz_mountain_architecture).

Peaks max-wins is applied by the caller (formPipeline light/coarse).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Hashable
from typing import TypeVar

from app.application.worldData.generators.terrain.mountains.rangeSideFill import (
    range_facing_wire_map,
    range_side_grades_at_points,
)
from app.application.worldData.generators.terrain.mountains.saddlePlacer import (
    resolve_saddle_rise_fraction,
    validate_saddle_peak_indices,
)
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec

KeyT = TypeVar("KeyT", bound=Hashable)

logger = logging.getLogger(__name__)


def modulate_saddles(
    fractions: dict[KeyT, float],
    points: list[tuple[KeyT, float, float]],
    spec: MountainRangeSpec,
    *,
    influence_m: float,
) -> None:
    """Dip corridor fractions toward saddle rise at each saddle."""
    peaks = list(spec.peaks)
    if not peaks or not spec.saddles:
        return
    n = len(peaks)
    point_xy = {key: (px, py) for key, px, py in points}
    for saddle in spec.saddles:
        validate_saddle_peak_indices(saddle, n)
        peak_a = peaks[saddle.peak_a_index]
        peak_b = peaks[saddle.peak_b_index]
        f = resolve_saddle_rise_fraction(
            saddle=saddle,
            range_fraction=spec.saddle_rise_fraction,
            peak_a=peak_a,
            peak_b=peak_b,
        )
        t = float(saddle.t)
        sx = peak_a.origin_x_m + (peak_b.origin_x_m - peak_a.origin_x_m) * t
        sy = peak_a.origin_y_m + (peak_b.origin_y_m - peak_a.origin_y_m) * t
        touched = 0
        for key, frac in list(fractions.items()):
            xy = point_xy.get(key)
            if xy is None:
                continue
            d = math.hypot(xy[0] - sx, xy[1] - sy)
            if d >= influence_m:
                continue
            cap = f + (1.0 - f) * (d / max(1e-6, influence_m))
            if frac > cap:
                fractions[key] = cap
                touched += 1
        logger.info(
            "relief_grade_spec | saddle a=%d b=%d t=%.2f f=%.2f pos=(%.0f,%.0f) dipped=%d",
            saddle.peak_a_index,
            saddle.peak_b_index,
            t,
            f,
            sx,
            sy,
            touched,
        )


def compose_range_corridor(
    spec: MountainRangeSpec,
    points: list[tuple[KeyT, float, float]],
    *,
    light_m: float,
) -> tuple[dict[KeyT, float], dict[KeyT, str | None]]:
    """U6 steps 1–2: corridor SideFill (+ facing) → saddle modulate.

    Returns ``(fractions, system_facing_wire)``. Caller overlays peaks max-wins.
    """
    grades = range_side_grades_at_points(spec, points, light_m=light_m)
    fractions = {k: float(g.fraction) for k, g in grades.items()}
    facing = range_facing_wire_map(grades)
    half = max(1, int(spec.width_m)) / 2.0
    modulate_saddles(
        fractions, points, spec, influence_m=float(max(1.0, half)),
    )
    if spec.saddles:
        logger.info(
            "relief_grade_spec | range saddles=%d U6 compose corridor→saddle",
            len(spec.saddles),
        )
    return fractions, facing
