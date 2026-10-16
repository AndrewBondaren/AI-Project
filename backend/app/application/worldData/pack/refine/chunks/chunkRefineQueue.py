"""Background chunk refine queue — WP-11 path-first."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field


@dataclass(order=True)
class _QueuedChunk:
    priority: float
    gx: int = field(compare=False)
    gy: int = field(compare=False)
    cx: int = field(compare=False)
    cy: int = field(compare=False)


class ChunkRefineQueue:
    def __init__(self, *, max_workers: int = 1) -> None:
        self._heap: list[_QueuedChunk] = []
        self._seen: set[tuple[int, int, int, int]] = set()
        self.max_workers = max(1, max_workers)

    def enqueue_chunk(
        self,
        gx: int,
        gy: int,
        cx: int,
        cy: int,
        *,
        anchor_x: float,
        anchor_y: float,
        chunk_columns: int,
        tile_size_m: int,
    ) -> bool:
        key = (gx, gy, cx, cy)
        if key in self._seen:
            return False
        center_x = gx * tile_size_m + (cx + 0.5) * chunk_columns
        center_y = gy * tile_size_m + (cy + 0.5) * chunk_columns
        dist = math.hypot(center_x - anchor_x, center_y - anchor_y)
        heapq.heappush(self._heap, _QueuedChunk(dist, gx, gy, cx, cy))
        self._seen.add(key)
        return True

    def pending_items(self) -> list[tuple[int, int, int, int, float]]:
        return [(item.gx, item.gy, item.cx, item.cy, item.priority) for item in self._heap]

    def pop_next(self) -> tuple[int, int, int, int] | None:
        if not self._heap:
            return None
        item = heapq.heappop(self._heap)
        return item.gx, item.gy, item.cx, item.cy

    def __len__(self) -> int:
        return len(self._heap)

    def pending_count(self) -> int:
        return len(self._heap)
