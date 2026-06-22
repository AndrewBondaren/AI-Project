"""
XY pathfinder for tunnel-like passages.

Used by UndergroundTunnelBuilder and CorridorConnector.
Z-constraints are the caller's responsibility: pre-encode them in the blocked set.

Algorithm: 0-1 BFS minimising direction changes (turns cost 1, straight moves cost 0).
"""
from __future__ import annotations

import logging
from collections import deque

logger = logging.getLogger(__name__)

_NEIGHBORS: tuple[tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))


class TunnelPathFinder:
    """
    0-1 BFS pathfinder for XY tunnel routing.

    find_path(start, target, blocked, bounds) → list[(x, y)]
      - Returns path from start to first reachable cell in target, inclusive.
      - Returns [] when no path exists.
      - target cells are always traversable even if also in blocked.
    """

    def find_path(
        self,
        start:   tuple[int, int],
        target:  set[tuple[int, int]],
        blocked: set[tuple[int, int]],
        bounds:  tuple[int, int, int, int] | None = None,
    ) -> list[tuple[int, int]]:
        """
        start   — starting XY cell (may be outside target/blocked)
        target  — acceptable destination cells
        blocked — impassable cells (target cells override this)
        bounds  — (min_x, min_y, max_x, max_y) hard search boundary;
                  auto-computed from start + target with margin when None
        """
        if not target:
            return []

        x_min, y_min, x_max, y_max = self._resolve_bounds(start, target, bounds)

        INF = float("inf")
        dist: dict[tuple[int, int, int], float] = {}
        prev: dict[tuple[int, int, int], tuple[int, int, int] | None] = {}

        start_key = (start[0], start[1], -1)
        dist[start_key] = 0.0
        prev[start_key] = None

        dq: deque[tuple[int, int, int]] = deque([start_key])
        found_key: tuple[int, int, int] | None = None

        while dq:
            cx, cy, cd = dq.popleft()
            cur_cost = dist.get((cx, cy, cd), INF)

            if (cx, cy) in target and cd != -1:
                found_key = (cx, cy, cd)
                break

            for di, (dx, dy) in enumerate(_NEIGHBORS):
                nx, ny = cx + dx, cy + dy
                if not (x_min <= nx <= x_max and y_min <= ny <= y_max):
                    continue
                if (nx, ny) in blocked and (nx, ny) not in target:
                    continue
                turn_cost = 0 if (cd == -1 or di == cd) else 1
                new_cost  = cur_cost + turn_cost
                key = (nx, ny, di)
                if new_cost < dist.get(key, INF):
                    dist[key] = new_cost
                    prev[key] = (cx, cy, cd)
                    if turn_cost == 0:
                        dq.appendleft(key)
                    else:
                        dq.append(key)

        if found_key is None:
            logger.debug(
                "TunnelPathFinder: no path from %s to target (%d cells)", start, len(target)
            )
            return []

        path: list[tuple[int, int, int]] = []
        key: tuple[int, int, int] | None = found_key
        while key is not None:
            path.append(key)
            key = prev.get(key)
        path.reverse()
        return [(x, y) for x, y, _ in path]

    @staticmethod
    def _resolve_bounds(
        start:  tuple[int, int],
        target: set[tuple[int, int]],
        bounds: tuple[int, int, int, int] | None,
    ) -> tuple[int, int, int, int]:
        if bounds is not None:
            return bounds
        all_x = [start[0]] + [x for x, _ in target]
        all_y = [start[1]] + [y for _, y in target]
        margin = max(max(all_x) - min(all_x), max(all_y) - min(all_y), 4)
        return min(all_x) - margin, min(all_y) - margin, max(all_x) + margin, max(all_y) + margin
