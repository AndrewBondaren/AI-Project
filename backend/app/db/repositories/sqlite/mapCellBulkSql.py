"""map_cells bulk persist — TR-PERF-1 consumer of ``app.db.bulkSql``."""

from __future__ import annotations

from app.db.bulkSql import EXECUTEMANY_BATCH_SIZE, executemany_rows
from app.db.models.mapCell import MapCell

__all__ = ["EXECUTEMANY_BATCH_SIZE", "executemany_cells"]


async def executemany_cells(conn, sql: str, cells: list[MapCell]) -> int:
    return await executemany_rows(conn, sql, cells)
