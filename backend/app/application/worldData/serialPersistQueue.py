"""Single-writer async consumer for MapCellService.save_pass."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.api.schemas.imports import ImportResult
from app.application.worldData.mapCellService import LayerKind, MapCellService
from app.db.models.mapCell import MapCell


class SerialPersistQueue:
    """Strictly serial persist — one active writer per queue instance."""

    def __init__(self, map_cell_service: MapCellService) -> None:
        self._map_cells = map_cell_service

    async def persist_stream(
        self,
        batches: AsyncIterator[tuple[LayerKind, list[MapCell]]],
    ) -> ImportResult:
        total = 0
        succeeded = 0
        async for layer, cells in batches:
            if not cells:
                continue
            total += len(cells)
            result = await self._map_cells.save_pass(cells, layer)
            succeeded += result.succeeded
        return ImportResult(total=total, succeeded=succeeded, failed=0)
