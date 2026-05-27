from app.db.database import Database
from app.db.models.sessionScene import SessionScene
from app.db.repositories.iSceneRepository import ISceneRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteSceneRepository(BaseRepository[SessionScene], ISceneRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, SessionScene)

    async def get(self, session_id: str) -> SessionScene | None:
        return await self.fetch_one("session_id = ?", [session_id])

    async def upsert(self, scene: SessionScene) -> None:
        await super().upsert(scene)
