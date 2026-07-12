"""Pending fine climate tiles for background bake — CL-PACK-2."""

from __future__ import annotations


class ClimateFinePending:
    """In-memory set of macro tiles awaiting denser climate bake."""

    def __init__(self) -> None:
        self._pending: set[tuple[int, int]] = set()

    def enqueue(self, gx: int, gy: int) -> bool:
        key = (gx, gy)
        if key in self._pending:
            return False
        self._pending.add(key)
        return True

    def pop_next(self) -> tuple[int, int] | None:
        if not self._pending:
            return None
        return self._pending.pop()

    def __len__(self) -> int:
        return len(self._pending)

    def clear(self) -> None:
        self._pending.clear()
