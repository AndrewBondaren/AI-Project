"""Batch SQL helpers for map_cells persist — TR-PERF-1."""

from __future__ import annotations

from app.db.mapper import to_row
from app.db.models.mapCell import MapCell

EXECUTEMANY_BATCH_SIZE = 5000


def cell_value_rows(cells: list[MapCell]) -> list[list[object]]:
    return [list(to_row(cell)[1]) for cell in cells]


async def executemany_cells(conn, sql: str, cells: list[MapCell]) -> int:
    """Run *sql* via executemany in sub-batches; return affected row estimate."""
    if not cells:
        return 0
    rows = cell_value_rows(cells)
    total = 0
    for offset in range(0, len(rows), EXECUTEMANY_BATCH_SIZE):
        batch = rows[offset : offset + EXECUTEMANY_BATCH_SIZE]
        cur = await conn.executemany(sql, batch)
        rc = cur.rowcount
        total += len(batch) if rc is None or rc < 0 else rc
    return total
