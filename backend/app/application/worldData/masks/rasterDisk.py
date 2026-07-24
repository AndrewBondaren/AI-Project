"""Shared disk raster in absolute light coords — tz_map_light_bake § MaskDomain materialize."""

from __future__ import annotations

from collections.abc import Iterable


def iter_disk_cells(cx: int, cy: int, radius: int) -> Iterable[tuple[int, int]]:
    r = max(0, int(radius))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            yield cx + dx, cy + dy


def raster_disk(cx: int, cy: int, radius: int) -> set[tuple[int, int]]:
    return set(iter_disk_cells(cx, cy, radius))
