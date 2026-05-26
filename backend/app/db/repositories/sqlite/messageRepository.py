from app.db.database import Database
from app.db.mapper import from_row
from app.db.models.message import Turn, Message, NodeExecutionLog
from app.db.repositories.iMessageRepository import IMessageRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteMessageRepository(IMessageRepository):

    def __init__(self, db: Database) -> None:
        self._db = db

    async def create_turn(self, turn: Turn) -> None:
        await BaseRepository(self._db, Turn).insert(turn)

    async def create_message(self, message: Message) -> None:
        await BaseRepository(self._db, Message).insert(message)

    async def create_node_log(self, log: NodeExecutionLog) -> None:
        await BaseRepository(self._db, NodeExecutionLog).insert(log)

    async def get_turns_by_session(self, session_id: str, limit: int | None = None) -> list[Turn]:
        if limit is None:
            sql = "SELECT * FROM turns WHERE session_id = ? ORDER BY created_at ASC"
            params = (session_id,)
        else:
            sql = """
                SELECT * FROM (
                    SELECT * FROM turns
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ) ORDER BY created_at ASC
            """
            params = (session_id, limit)
        async with self._db.conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [from_row(Turn, r) for r in rows]

    async def get_messages_by_turn(self, turn_id: str) -> list[Message]:
        async with self._db.conn.execute(
            "SELECT * FROM messages WHERE turn_id = ? ORDER BY created_at ASC",
            (turn_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [from_row(Message, r) for r in rows]

    async def get_history(self, session_id: str, limit: int | None = None) -> list[dict]:
        if limit is None:
            sql = """
                SELECT t.player_input, m.llm_output
                FROM turns t
                LEFT JOIN messages m ON m.turn_id = t.turn_id AND m.message_type = 'narrative'
                WHERE t.session_id = ?
                ORDER BY t.created_at ASC
            """
            params = (session_id,)
        else:
            sql = """
                SELECT t.player_input, m.llm_output
                FROM (
                    SELECT turn_id, player_input, created_at
                    FROM turns
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ) t
                LEFT JOIN messages m ON m.turn_id = t.turn_id AND m.message_type = 'narrative'
                ORDER BY t.created_at ASC
            """
            params = (session_id, limit)
        async with self._db.conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        result = []
        for row in rows:
            result.append({"role": "user", "text": row["player_input"]})
            if row["llm_output"]:
                result.append({"role": "bot", "text": row["llm_output"]})
        return result
