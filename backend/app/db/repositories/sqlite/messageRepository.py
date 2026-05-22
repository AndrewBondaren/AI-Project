from app.db.database import Database
from app.db.mapper import from_row
from app.db.models.message import Message
from app.db.repositories.iMessageRepository import IMessageRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteMessageRepository(BaseRepository[Message], IMessageRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, Message)

    async def create(self, message: Message) -> None:
        await self.insert(message)

    async def get_by_session(self, session_id: str, limit: int | None = None) -> list[Message]:
        if limit is None:
            async with self._db.conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ) as cur:
                rows = await cur.fetchall()
            return [from_row(Message, r) for r in rows]

        async with self._db.conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ) ORDER BY created_at ASC
            """,
            (session_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [from_row(Message, r) for r in rows]
