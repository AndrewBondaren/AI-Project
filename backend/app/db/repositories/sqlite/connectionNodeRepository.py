from app.db.database import Database, _in_transaction
from app.db.models.connectionNode import ConnectionNode
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteConnectionNodeRepository(BaseRepository[ConnectionNode], IConnectionNodeRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, ConnectionNode)

    async def get_by_id(self, node_uid: str) -> ConnectionNode | None:
        return await self.fetch_one("node_uid = ?", [node_uid])

    async def get_by_world(self, world_uid: str) -> list[ConnectionNode]:
        return await self.fetch_all("world_uid = ?", [world_uid])

    async def upsert(self, node: ConnectionNode) -> None:
        await super().upsert(node)

    async def upsert_bulk(self, nodes: list[ConnectionNode]) -> int:
        if not nodes:
            return 0
        async with self._db.transaction():
            for node in nodes:
                await self.upsert(node)
        return len(nodes)

    async def delete_by_world(self, world_uid: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM connection_nodes WHERE world_uid = ?",
            [world_uid],
        )
        if not _in_transaction.get():
            await self._db.conn.commit()
