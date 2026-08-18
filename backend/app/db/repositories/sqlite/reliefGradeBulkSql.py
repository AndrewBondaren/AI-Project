"""Batch SQL helpers for relief grade catalog persist — R43 (not map_cells)."""

from __future__ import annotations

from collections.abc import Sequence

from app.db.mapper import to_row

EXECUTEMANY_BATCH_SIZE = 5000
UID_IN_BATCH_SIZE = 400


def value_rows(objs: Sequence[object]) -> list[list[object]]:
    return [list(to_row(obj)[1]) for obj in objs]


async def executemany_rows(conn, sql: str, objs: Sequence[object]) -> int:
    """Run *sql* via executemany in sub-batches; return affected row estimate."""
    if not objs:
        return 0
    rows = value_rows(objs)
    total = 0
    for offset in range(0, len(rows), EXECUTEMANY_BATCH_SIZE):
        batch = rows[offset : offset + EXECUTEMANY_BATCH_SIZE]
        cur = await conn.executemany(sql, batch)
        rc = cur.rowcount
        total += len(batch) if rc is None or rc < 0 else rc
    return total
