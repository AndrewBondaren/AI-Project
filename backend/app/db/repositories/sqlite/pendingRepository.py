from datetime import datetime, timezone

from app.db.database import Database
from app.db.mapper import from_row
from app.db.models.sessionPending import SessionPending
from app.db.repositories.iPendingRepository import IPendingRepository


class SqlitePendingRepository(IPendingRepository):

    def __init__(self, db: Database) -> None:
        self._db = db

    async def upsert(self, session_id: str, player_input: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.conn.execute(
            "INSERT OR REPLACE INTO session_pending (session_id, player_input, created_at) VALUES (?, ?, ?)",
            (session_id, player_input, now),
        )
        await self._db.conn.commit()

    async def update_snapshot(self, session_id: str, snapshot_json: str) -> None:
        await self._db.conn.execute(
            "UPDATE session_pending SET snapshot = ? WHERE session_id = ?",
            (snapshot_json, session_id),
        )
        await self._db.conn.commit()

    async def get(self, session_id: str) -> SessionPending | None:
        async with self._db.conn.execute(
            "SELECT * FROM session_pending WHERE session_id = ?", (session_id,)
        ) as cur:
            row = await cur.fetchone()
        return from_row(SessionPending, row) if row else None

    async def delete(self, session_id: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM session_pending WHERE session_id = ?", (session_id,)
        )
        await self._db.conn.commit()

    async def cleanup_stale(self) -> None:
        await self._db.conn.execute("""
            DELETE FROM session_pending
            WHERE EXISTS (
                SELECT 1 FROM turns
                WHERE turns.session_id   = session_pending.session_id
                AND   turns.player_input = session_pending.player_input
                AND   turns.created_at  >= session_pending.created_at
            )
        """)
        await self._db.conn.commit()
