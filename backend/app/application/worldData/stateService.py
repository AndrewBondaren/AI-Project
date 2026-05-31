from fastapi import HTTPException

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list
from app.db.models.state import State
from app.db.repositories.iStateRepository import IStateRepository


class StateService:

    def __init__(self, repo: IStateRepository) -> None:
        self._repo = repo

    async def get_all(self, world_uid: str) -> list[State]:
        return await self._repo.get_by_world(world_uid)

    async def get_by_id(self, world_uid: str, state_uid: str) -> State:
        state = await self._repo.get_by_id(state_uid)
        if state is None or state.world_uid != world_uid:
            raise HTTPException(status_code=404, detail=f"State '{state_uid}' not found")
        return state

    async def get_by_uids(self, uids: list[str]) -> list[State]:
        return await self._repo.get_by_uids(uids)

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        def prepare(row: dict) -> State:
            return State(**{**row, "world_uid": world_uid})
        return await import_list(data, prepare, self._repo.upsert)
