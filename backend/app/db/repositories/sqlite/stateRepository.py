from app.db.database import Database
from app.db.models.state import State
from app.db.repositories.iStateRepository import IStateRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteStateRepository(BaseRepository[State], IStateRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, State)

    async def get_by_id(self, state_uid: str) -> State | None:
        return await self.fetch_one("state_uid = ?", [state_uid])

    async def get_by_world(self, world_uid: str) -> list[State]:
        return await self.fetch_all("world_uid = ?", [world_uid], order="display_name ASC")

    async def get_by_uids(self, uids: list[str]) -> list[State]:
        if not uids:
            return []
        placeholders = ",".join("?" * len(uids))
        return await self.fetch_all(f"state_uid IN ({placeholders})", uids)

    async def upsert(self, state: State) -> None:
        await super().upsert(state)

    async def delete(self, state_uid: str) -> None:
        await super().delete(state_uid)
