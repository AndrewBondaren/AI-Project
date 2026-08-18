"""Shared bulk SQL — one batch size, one executemany loop.

Consumers (map_cells, relief grades, persist heartbeat) pass SQL + rows.
See tz_terrain_generation TR-PERF-1, tz_terrain_relief R43.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TypeVar

from app.db.mapper import to_row

EXECUTEMANY_BATCH_SIZE = 5000

T = TypeVar("T")


def iter_batches(
    items: Sequence[T],
    *,
    size: int = EXECUTEMANY_BATCH_SIZE,
) -> Iterator[Sequence[T]]:
    """Yield consecutive slices of *items*; empty input yields nothing."""
    if not items:
        return
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


def value_rows(objs: Sequence[object]) -> list[list[object]]:
    return [list(to_row(obj)[1]) for obj in objs]


async def executemany_rows(conn, sql: str, objs: Sequence[object]) -> int:
    """Run *sql* via executemany in sub-batches; return affected row estimate."""
    if not objs:
        return 0
    rows = value_rows(objs)
    total = 0
    for batch in iter_batches(rows):
        cur = await conn.executemany(sql, batch)
        rc = cur.rowcount
        total += len(batch) if rc is None or rc < 0 else rc
    return total
