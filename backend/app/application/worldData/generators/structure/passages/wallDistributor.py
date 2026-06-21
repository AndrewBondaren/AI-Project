"""
Distribution strategies for wall openings.

Each StructureElement opening type maps to a WallDistributor that decides
how groups of cells are selected from a filtered wall-cell list.

Inputs are already filtered (corners excluded, doors excluded ±1).
Output: list of groups; each group is a list of (x, y) cells.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from random import Random

from app.application.worldData.generators.structure.structureElement import StructureElement


# ---------------------------------------------------------------------------
# Shared primitives

def _split_into_segments(
    cells: list[tuple[int, int]],
) -> list[list[tuple[int, int]]]:
    """Split a sorted cell list into contiguous runs (gaps come from door exclusions)."""
    if not cells:
        return []
    segments: list[list[tuple[int, int]]] = []
    current = [cells[0]]
    for prev, curr in zip(cells, cells[1:]):
        if abs(curr[0] - prev[0]) + abs(curr[1] - prev[1]) == 1:
            current.append(curr)
        else:
            segments.append(current)
            current = [curr]
    segments.append(current)
    return segments


def _symmetric_placement(
    available: list[tuple[int, int]],
    count: int,
    size: int,
    spacing: int = 1,
) -> list[list[tuple[int, int]]]:
    max_count = (len(available) + spacing) // (size + spacing)
    actual = min(count, max_count)
    if actual <= 0:
        return []
    total_w = actual * size + (actual - 1) * spacing
    start = (len(available) - total_w) // 2
    return [available[start + i * (size + spacing): start + i * (size + spacing) + size]
            for i in range(actual)]


def _distribute_count(count: int, segments: list[list]) -> list[int]:
    """Distribute count across segments proportionally to their length."""
    total = sum(len(s) for s in segments)
    if not segments or total == 0:
        return [0] * len(segments)
    counts: list[int] = []
    remaining = count
    for seg in segments[:-1]:
        n = min(max(0, round(count * len(seg) / total)), remaining)
        counts.append(n)
        remaining -= n
    counts.append(max(0, remaining))
    return counts


# ---------------------------------------------------------------------------
# Base

class WallDistributor(ABC):
    @abstractmethod
    def place(
        self,
        wall_cells: list[tuple[int, int]],
        count: int,
        size: int,
        distribution: str,
        rng: Random,
    ) -> list[list[tuple[int, int]]]:
        """Return groups of (x, y) to place openings at. Empty group = skip."""
        ...


# ---------------------------------------------------------------------------
# Strategies

class SegmentedDistributor(WallDistributor):
    """
    Spreads openings evenly across door-bounded segments.
    Used for: window, porthole, vent.
    """

    def place(
        self,
        wall_cells: list[tuple[int, int]],
        count: int,
        size: int,
        distribution: str,
        rng: Random,
    ) -> list[list[tuple[int, int]]]:
        segments = _split_into_segments(wall_cells)
        seg_counts = _distribute_count(count, segments)
        groups: list[list[tuple[int, int]]] = []
        for seg, seg_count in zip(segments, seg_counts):
            if seg_count == 0:
                continue
            if distribution == "random":
                rng.shuffle(seg)
            groups.extend(_symmetric_placement(seg, seg_count, size, spacing=1))
        return groups


class SolidRunDistributor(WallDistributor):
    """
    Places openings as one dense continuous block (no spacing between units).
    Targets the longest available segment.
    Used for: arrow_slit.
    """

    def place(
        self,
        wall_cells: list[tuple[int, int]],
        count: int,
        size: int,
        distribution: str,
        rng: Random,
    ) -> list[list[tuple[int, int]]]:
        segments = _split_into_segments(wall_cells)
        if not segments:
            return []
        target = max(segments, key=len)
        total_w = count * size
        if total_w > len(target):
            count = len(target) // size
            total_w = count * size
        if count <= 0:
            return []
        if distribution == "random":
            max_start = len(target) - total_w
            start = rng.randint(0, max_start) if max_start > 0 else 0
        else:
            start = (len(target) - total_w) // 2
        return [target[start + i * size: start + i * size + size] for i in range(count)]


class CenteredDistributor(WallDistributor):
    """
    Symmetric placement on the full flat wall (ignores door-segment boundaries).

    count=1  →  # # # W # # #   (one block at center)
    count=2  →  # W # # # W #   (two blocks symmetric around center)

    Selected by distribution="centered", overrides the type-based distributor.
    """

    def place(
        self,
        wall_cells: list[tuple[int, int]],
        count: int,
        size: int,
        distribution: str,
        rng: Random,
    ) -> list[list[tuple[int, int]]]:
        if not wall_cells:
            return []
        return _symmetric_placement(wall_cells, count, size, spacing=1)


# ---------------------------------------------------------------------------
# Registry

_SEGMENTED  = SegmentedDistributor()
_SOLID_RUN  = SolidRunDistributor()
_CENTERED   = CenteredDistributor()

# Selected by opening_type (default when distribution != "centered")
DISTRIBUTOR_BY_TYPE: dict[StructureElement, WallDistributor] = {
    StructureElement.WINDOW:     _SEGMENTED,
    StructureElement.PORTHOLE:   _SEGMENTED,
    StructureElement.VENT:       _SEGMENTED,
    StructureElement.ARROW_SLIT: _SOLID_RUN,
}

# Overrides type-based selection when distribution field matches
DISTRIBUTOR_BY_DISTRIBUTION: dict[str, WallDistributor] = {
    "centered": _CENTERED,
}
