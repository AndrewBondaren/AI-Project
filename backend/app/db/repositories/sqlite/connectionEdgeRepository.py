from app.db.database import Database, _in_transaction
from app.db.models.connectionEdge import ConnectionEdge
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteConnectionEdgeRepository(BaseRepository[ConnectionEdge], IConnectionEdgeRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, ConnectionEdge)

    async def get_by_id(self, edge_uid: str) -> ConnectionEdge | None:
        return await self.fetch_one("edge_uid = ?", [edge_uid])

    async def get_by_world(self, world_uid: str) -> list[ConnectionEdge]:
        return await self.fetch_all("world_uid = ?", [world_uid])

    async def upsert(self, edge: ConnectionEdge) -> None:
        await super().upsert(edge)

    async def upsert_bulk(self, edges: list[ConnectionEdge]) -> int:
        if not edges:
            return 0
        async with self._db.transaction():
            for edge in edges:
                await self.upsert(edge)
        return len(edges)

    async def delete_by_world(self, world_uid: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM connection_edges WHERE world_uid = ?",
            [world_uid],
        )
        if not _in_transaction.get():
            await self._db.conn.commit()
