"""CPU-sum timings for relief discover mill + L2 paint (seconds).

Q1/Q2 and mill parts are summed across chunks and can exceed wall ``l2_s``
when workers > 1. SoT generate: ``docs/tz_terrain_relief.md`` R41.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any


def _r(value: float) -> float:
    return round(float(value), 3)


@dataclass(frozen=True, slots=True)
class GradePipelineTimings:
    q1_s: float = 0.0
    q2_s: float = 0.0
    mill_setup_s: float = 0.0
    mill_sheer_s: float = 0.0
    mill_seam_s: float = 0.0
    mill_reconcile_s: float = 0.0
    mill_s: float = 0.0
    grade_setup_s: float = 0.0
    paint_s: float = 0.0
    seams_s: float = 0.0
    grade_s: float = 0.0
    materialize_s: float = 0.0
    sidecar_s: float = 0.0
    validate_s: float = 0.0
    systems_emit_s: float = 0.0

    @property
    def q_total_s(self) -> float:
        return self.q1_s + self.q2_s

    def added(self, other: GradePipelineTimings) -> GradePipelineTimings:
        return GradePipelineTimings(
            **{
                item.name: getattr(self, item.name) + getattr(other, item.name)
                for item in fields(self)
            },
        )

    def with_wall(
        self,
        *,
        sidecar_s: float = 0.0,
        validate_s: float = 0.0,
        systems_emit_s: float = 0.0,
    ) -> GradePipelineTimings:
        return replace(
            self,
            sidecar_s=sidecar_s,
            validate_s=validate_s,
            systems_emit_s=systems_emit_s,
        )

    def as_dict(self) -> dict[str, float]:
        payload = {item.name: _r(getattr(self, item.name)) for item in fields(self)}
        payload["q_total_s"] = _r(self.q_total_s)
        return payload

    def mill_log_fields(self) -> dict[str, Any]:
        """JSON extras that do not collide with existing ``grade_s`` / ``materialize_s``."""
        omit = frozenset({"grade_s", "materialize_s"})
        return {key: value for key, value in self.as_dict().items() if key not in omit}

    @classmethod
    def wire_keys(cls) -> tuple[str, ...]:
        return tuple(item.name for item in fields(cls)) + ("q_total_s",)

    def log_suffix(self) -> str:
        d = self.as_dict()
        return (
            f" q1_s={d['q1_s']:.2f} q2_s={d['q2_s']:.2f}"
            f" q_total_s={d['q_total_s']:.2f} mill_s={d['mill_s']:.2f}"
            f" paint_s={d['paint_s']:.2f}"
        )
