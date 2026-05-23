from datetime import datetime, timezone

from app.db.database import Database
from app.db.models.gameSession import GameSession
from app.db.models.sessionSummary import SessionSummary
from app.db.repositories.iSessionRepository import ISessionRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteSessionRepository(BaseRepository[GameSession], ISessionRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, GameSession)

    async def get_all_enriched(self) -> list[SessionSummary]:
        sql = """
            SELECT gs.id,
                   gs.world_uid,
                   gs.player_character_id AS character_id,
                   gs.last_active_at,
                   w.name                AS world_name,
                   p.display_name        AS character_name
            FROM game_sessions gs
            LEFT JOIN worlds          w ON w.world_uid    = gs.world_uid
            LEFT JOIN character_sheet p ON p.character_uid = gs.player_character_id
            ORDER BY gs.last_active_at DESC
        """
        async with self._db.conn.execute(sql) as cur:
            rows = await cur.fetchall()
        return [SessionSummary(**dict(row)) for row in rows]

    async def get_by_id(self, session_id: str) -> GameSession | None:
        return await self.fetch_one("id = ?", [session_id])

    async def get_by_world_and_character(
        self, world_uid: str, character_id: str
    ) -> GameSession | None:
        return await self.fetch_one(
            "world_uid = ? AND player_character_id = ?",
            [world_uid, character_id],
        )

    async def create(self, session: GameSession) -> None:
        await self.insert(session)

    async def touch(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.conn.execute(
            "UPDATE game_sessions SET last_active_at = ? WHERE id = ?",
            (now, session_id),
        )
        await self._db.conn.commit()

    async def get_participants(self, session_id: str) -> list[str]:
        async with self._db.conn.execute(
            "SELECT character_uid FROM scene_participants WHERE session_id = ?",
            (session_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [r["character_uid"] for r in rows]

    async def add_participant(self, session_id: str, character_uid: str) -> None:
        await self._db.conn.execute(
            "INSERT OR IGNORE INTO scene_participants (session_id, character_uid) VALUES (?, ?)",
            (session_id, character_uid),
        )
        await self._db.conn.commit()

    async def remove_participant(self, session_id: str, character_uid: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM scene_participants WHERE session_id = ? AND character_uid = ?",
            (session_id, character_uid),
        )
        await self._db.conn.commit()

    async def clear_participants(self, session_id: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM scene_participants WHERE session_id = ?",
            (session_id,),
        )
        await self._db.conn.commit()
