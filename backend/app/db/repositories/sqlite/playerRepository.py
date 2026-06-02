import dataclasses

from app.db.database import Database
from app.db.mapper import from_row
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

    async def get_all_enriched(self) -> list[dict]:
        sql = """
            SELECT cs.*,
                   s.id        AS _session_id,
                   s.world_uid AS _world_uid,
                   w.name      AS _world_name
            FROM character_sheet cs
            LEFT JOIN (
                SELECT gs.player_character_id, gs.id, gs.world_uid
                FROM game_sessions gs
                INNER JOIN (
                    SELECT player_character_id, MAX(last_active_at) AS max_ts
                    FROM game_sessions
                    GROUP BY player_character_id
                ) mx ON gs.player_character_id = mx.player_character_id
                      AND gs.last_active_at = mx.max_ts
            ) s ON s.player_character_id = cs.character_uid
            LEFT JOIN worlds w ON w.world_uid = s.world_uid
            WHERE cs.character_type = 'player'
            ORDER BY cs.created_at DESC
        """
        async with self._db.conn.execute(sql) as cur:
            rows = await cur.fetchall()
        result = []
        for row in rows:
            d = dataclasses.asdict(from_row(Player, row))
            session_id = row["_session_id"]
            d["active_session"] = {
                "session_id": session_id,
                "world_uid":  row["_world_uid"],
                "world_name": row["_world_name"],
            } if session_id else None
            result.append(d)
        return result

    async def create(self, player: Player) -> None:
        await self.insert(player)

    async def update(self, player: Player) -> None:
        await self.save(player)
