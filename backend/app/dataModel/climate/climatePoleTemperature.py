"""Derived pole base temperature from peak band — tz_climate.md § Derived temp."""

from __future__ import annotations

from typing import Any

POLE_TEMPERATURE_INSET_FRACTION = 0.2


def _pole_kind_wire(pole_kind: Any) -> str:
    wire = getattr(pole_kind, "wire_value", pole_kind)
    return str(wire).strip().lower()


def derived_pole_temperature(pole_kind: Any, peak_min: int, peak_max: int) -> int:
    span = peak_max - peak_min
    kind = _pole_kind_wire(pole_kind)
    if kind == "hot":
        return round(peak_max - POLE_TEMPERATURE_INSET_FRACTION * span)
    if kind == "cold":
        return round(peak_min + POLE_TEMPERATURE_INSET_FRACTION * span)
    return round((peak_min + peak_max) / 2)
