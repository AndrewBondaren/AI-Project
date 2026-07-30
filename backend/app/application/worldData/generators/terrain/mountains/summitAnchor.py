"""SummitAnchor — Spec → vertex meters (tz_mountain_architecture)."""

from __future__ import annotations

from app.dataModel.terrainMasks.mountain.specs import MountainSpec, PlateauForm


def summit_anchor(spec: MountainSpec) -> tuple[float, float]:
    """L0 topology vertex ≈ Spec origin (plateau hat is not a separate ridge vertex)."""
    return float(spec.origin_x_m), float(spec.origin_y_m)


def summit_hat_radius_m(spec: MountainSpec) -> float | None:
    if isinstance(spec.form, PlateauForm):
        return float(spec.radius_m) * float(spec.form.hat_fraction)
    return None
