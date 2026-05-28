from app.db.database import Database
from app.db.models.npc import Npc
from app.db.repositories.iNpcRepository import INpcRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteNpcRepository(BaseRepository[Npc], INpcRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, Npc)

    async def get_by_id(self, character_uid: str) -> Npc | None:
        return await self.fetch_one("character_uid = ?", [character_uid])

    async def get_by_world(self, world_uid: str) -> list[Npc]:
        return await self.fetch_all("world_uid = ?", [world_uid])

    async def get_by_location(self, world_uid: str, location: str) -> list[Npc]:
        return await self.fetch_all(
            "world_uid = ? AND system_location = ?",
            [world_uid, location],
        )

    async def create(self, npc: Npc) -> None:
        await self.insert(npc)

    async def update(self, npc: Npc) -> None:
        await self.save(npc)

    async def convert_from_player(self, character_uid: str, world_uid: str) -> None:
        await self._db.conn.execute(
            """
            UPDATE character_sheet
            SET character_type = 'npc', world_uid = ?
            WHERE character_uid = ? AND character_type = 'player'
            """,
            (world_uid, character_uid),
        )
        await self._db.conn.commit()

    async def get_home_occupied_uids(self, world_uid: str, location_uids: list[str]) -> set[str]:
        if not location_uids:
            return set()
        placeholders = ", ".join("?" * len(location_uids))
        sql = (
            f"SELECT DISTINCT home_location_uid FROM character_sheet "
            f"WHERE character_type = 'npc' AND world_uid = ? "
            f"AND home_location_uid IN ({placeholders})"
        )
        async with self._db.conn.execute(sql, [world_uid, *location_uids]) as cur:
            rows = await cur.fetchall()
        return {row[0] for row in rows if row[0]}

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
