"""Bootstrap bulk persist port for materialize-stack — TR-PAR-6.

Scope: ``materialize-stack`` / ``save_terrain_batch`` bootstrap path only.
OLTP (gameplay, lazy, debug slices) uses ``MapCellService`` on ``main_conn``.

See ``docs/tz_terrain_generation.md`` § TR-PAR-6.
"""

import logging
import warnings

from contextlib import asynccontextmanager

from app.db.database import Database
from app.db.models.mapCell import MapCell
from app.db.repositories.iMapCellRepository import IMapCellRepository

logger = logging.getLogger(__name__)


class BootstrapMapCellWriter:
    """Explicit bulk writer on ``Database.bootstrap_conn``."""

    def __init__(self, db: Database, repo: IMapCellRepository) -> None:
        self._db = db
        self._repo = repo

    @asynccontextmanager
    async def session(self, *, enabled: bool = True):
        """Acquire bulk write lock when ``enabled``; caller must be inside for writes."""
        if not enabled:
            yield self
            return
        async with self._db.bulk_write_lock():
            yield self

    @property
    def _conn(self):
        return self._db.bootstrap_conn

    async def write_terrain(self, cells: list[MapCell], *, insert_only: bool) -> int:
        warnings.warn(
            "BootstrapMapCellWriter.write_terrain is deprecated — use WorldPackWriter (TR-PACK)",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning("legacy terrain bootstrap write (%d cells) — prefer pack bake", len(cells))
        if insert_only:
            return await self._repo.insert_terrain_bulk(cells, conn=self._conn)
        return await self._repo.upsert_terrain_skeleton(cells, conn=self._conn)

    async def write_terrain_chunk_batch(
        self,
        chunks: list[list[MapCell]],
        *,
        insert_only: bool,
    ) -> int:
        """TR-PERF-2: one transaction for multiple terrain chunk writes."""
        if not chunks:
            return 0
        total = 0
        async with self._db.transaction_on(self._conn):
            for cells in chunks:
                total += await self.write_terrain(cells, insert_only=insert_only)
        return total

    async def write_climate(self, cells: list[MapCell]) -> int:
        return await self._repo.upsert_climate_fields(cells, conn=self._conn)
