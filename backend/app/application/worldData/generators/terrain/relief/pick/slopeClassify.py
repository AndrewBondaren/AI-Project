"""classify(dz, schedule) — single path (I8)."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.log.log import relief_debug
from app.dataModel.terrain.relief.enums import ReliefSlopePolicy
from app.dataModel.terrain.relief.reliefDeltaSchedule import (
    ReliefDeltaInterval,
    ReliefDeltaSchedule,
)


@dataclass(frozen=True, slots=True)
class ClassifyResult:
    policy: ReliefSlopePolicy
    knobs: ReliefDeltaInterval | None
    reason: str


def classify(dz: int, schedule: ReliefDeltaSchedule) -> ClassifyResult | None:
    """Return policy+knobs, or None if hole in schedule (caller → R21)."""
    abs_dz = abs(dz)
    if abs_dz <= schedule.none_max_abs:
        result = ClassifyResult(
            policy=ReliefSlopePolicy.SLOPE_NONE,
            knobs=schedule.none_knobs,
            reason=f"abs(dz)={abs_dz}<=none_max={schedule.none_max_abs}",
        )
        relief_debug("classify", dz=dz, policy=result.policy.value, reason=result.reason)
        return result

    if dz > 0:
        band = _match_band(dz, schedule.down)
        if band is None:
            relief_debug("classify_hole", dz=dz, direction="down")
            return None
        result = ClassifyResult(
            policy=ReliefSlopePolicy.SLOPE_DOWN,
            knobs=band,
            reason=f"dz={dz} in down band [{band.value_min},{band.value_max}]",
        )
        relief_debug(
            "classify",
            dz=dz,
            policy=result.policy.value,
            slope_weight=band.slope_weight,
            sheer_weight=band.sheer_weight,
            reason=result.reason,
        )
        return result

    if dz < 0:
        mag = -dz
        band = _match_band(mag, schedule.up)
        if band is None:
            relief_debug("classify_hole", dz=dz, direction="up")
            return None
        result = ClassifyResult(
            policy=ReliefSlopePolicy.SLOPE_UP,
            knobs=band,
            reason=f"-dz={mag} in up band [{band.value_min},{band.value_max}]",
        )
        relief_debug(
            "classify",
            dz=dz,
            policy=result.policy.value,
            slope_weight=band.slope_weight,
            sheer_weight=band.sheer_weight,
            reason=result.reason,
        )
        return result

    return ClassifyResult(
        policy=ReliefSlopePolicy.SLOPE_NONE,
        knobs=schedule.none_knobs,
        reason="dz=0",
    )


def _match_band(value: int, bands: tuple[ReliefDeltaInterval, ...]) -> ReliefDeltaInterval | None:
    for band in bands:
        if value < band.value_min:
            continue
        if band.value_max is not None and value > band.value_max:
            continue
        return band
    return None
