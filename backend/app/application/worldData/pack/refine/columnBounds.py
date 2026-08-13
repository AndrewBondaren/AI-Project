"""Rect bounds Protocol — leaf (no terrain.types / climate import). R36v-T-4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ColumnBounds(Protocol):
    x_min: int
    x_max: int
    y_min: int
    y_max: int


@dataclass(frozen=True, slots=True)
class HaloRect:
    """Concrete bounds when ``ColumnRect`` cannot be imported (cycle)."""

    x_min: int
    x_max: int
    y_min: int
    y_max: int


def rect_contains(rect: ColumnBounds, x: int, y: int) -> bool:
    return rect.x_min <= x <= rect.x_max and rect.y_min <= y <= rect.y_max


def expand_rect(rect: ColumnBounds, halo: int) -> ColumnBounds:
    if halo <= 0:
        return rect
    return HaloRect(
        x_min=rect.x_min - halo,
        x_max=rect.x_max + halo,
        y_min=rect.y_min - halo,
        y_max=rect.y_max + halo,
    )
