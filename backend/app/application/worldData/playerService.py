import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.db.models.player import Player
from app.db.repositories.iPlayerRepository import IPlayerRepository


class PlayerService:

    def __init__(self, repo: IPlayerRepository) -> None:
        self._repo = repo

    async def get_all(self, world_uid: str | None = None) -> list[Player]:
        if world_uid is not None:
            return await self._repo.get_by_world(world_uid)
        return await self._repo.get_all()

    async def get_by_id(self, character_uid: str) -> Player:
        player = await self._repo.get_by_id(character_uid)
        if player is None:
            raise HTTPException(status_code=404, detail=f"Character '{character_uid}' not found")
        return player

    async def create(self, data: dict) -> Player:
        data = {
            "character_uid": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        player = Player(**data)
        await self._repo.create(player)
        return player

    async def delete(self, character_uid: str) -> None:
        await self.get_by_id(character_uid)
        await self._repo.delete(character_uid)
