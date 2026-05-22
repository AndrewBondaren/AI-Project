from app.db.database import Database
from app.db.models.npc import Npc
from app.db.repositories.iNpcRepository import INpcRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteNpcRepository(BaseRepository[Npc], INpcRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, Npc)

    async def get_by_id(self, character_uid: str) -> Npc | None:
        return await self.fetch_one("character_uid = ?", [character_uid])

    async def get_by_world(self, world_id: str) -> list[Npc]:
        return await self.fetch_all("world_id = ?", [world_id])

    async def get_by_location(self, world_id: str, location: str) -> list[Npc]:
        return await self.fetch_all(
            "world_id = ? AND system_location = ?",
            [world_id, location],
        )

    async def create(self, npc: Npc) -> None:
        await self.insert(npc)

    async def update(self, npc: Npc) -> None:
        await self.save(npc)

    async def convert_from_player(self, character_uid: str, world_id: str) -> None:
        await self._db.conn.execute(
            """
            UPDATE character_sheet
            SET character_type = 'npc', world_id = ?
            WHERE character_uid = ? AND character_type = 'player'
            """,
            (world_id, character_uid),
        )
        await self._db.conn.commit()

    async def clear_scene_state(self, character_uid: str) -> None:
        await self._db.conn.execute(
            """
            UPDATE character_sheet
            SET system_current_target    = NULL,
                system_current_thoughts  = NULL,
                display_current_thoughts = NULL
            WHERE character_uid = ? AND character_type = 'npc'
            """,
            (character_uid,),
        )
        await self._db.conn.commit()
