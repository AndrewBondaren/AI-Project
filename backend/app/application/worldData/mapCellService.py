from dataclasses import asdict

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list
from app.db.models.mapCell import MapCell
from app.db.repositories.iMapCellRepository import IMapCellRepository


class MapCellService:

    def __init__(self, repo: IMapCellRepository) -> None:
        self._repo = repo

    async def get_all(self, world_uid: str) -> list[MapCell]:
        return await self._repo.get_by_world(world_uid)

    async def export(self, world_uid: str) -> list[dict]:
        cells = await self._repo.get_by_world(world_uid)
        return [asdict(c) for c in cells]

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        def prepare(row: dict) -> MapCell:
            return MapCell(**{**row, "world_uid": world_uid})
        return await import_list(data, prepare, self._repo.upsert)

    async def clear(self, world_uid: str) -> None:
        await self._repo.delete_by_world(world_uid)
