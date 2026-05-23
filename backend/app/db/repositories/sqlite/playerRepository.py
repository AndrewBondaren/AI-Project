from app.db.database import Database
from app.db.models.player import Player
from app.db.repositories.iPlayerRepository import IPlayerRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqlitePlayerRepository(BaseRepository[Player], IPlayerRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, Player)

    async def get_by_id(self, character_uid: str) -> Player | None:
        return await self.fetch_one("character_uid = ?", [character_uid])

    async def get_all(self) -> list[Player]:
        return await self.fetch_all(order="created_at DESC")

    async def get_by_world(self, world_uid: str) -> list[Player]:
        return await self.fetch_all("world_uid = ?", [world_uid], order="created_at DESC")

    async def create(self, player: Player) -> None:
        await self.insert(player)

    async def update(self, player: Player) -> None:
        await self.save(player)
