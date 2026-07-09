from app.db.database import Database, _in_transaction
from app.db.models.connectionEdgeCell import ConnectionEdgeCell
from app.db.repositories.iConnectionEdgeCellRepository import IConnectionEdgeCellRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteConnectionEdgeCellRepository(BaseRepository[ConnectionEdgeCell], IConnectionEdgeCellRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, ConnectionEdgeCell)

    async def get_by_edge(self, edge_uid: str) -> list[ConnectionEdgeCell]:
        return await self.fetch_all("edge_uid = ?", [edge_uid], order="seq ASC")

    async def replace_for_edge(self, edge_uid: str, cells: list[ConnectionEdgeCell]) -> int:
        async with self._db.transaction():
            await self._db.conn.execute(
                "DELETE FROM connection_edge_cells WHERE edge_uid = ?",
                [edge_uid],
            )
            for cell in cells:
                await self.upsert(cell)
        return len(cells)

    async def upsert_bulk(self, cells: list[ConnectionEdgeCell]) -> int:
        if not cells:
            return 0
        async with self._db.transaction():
            for cell in cells:
                await self.upsert(cell)
        return len(cells)

    async def delete_by_world(self, world_uid: str) -> None:
        await self._db.conn.execute(
            "DELETE FROM connection_edge_cells WHERE edge_uid IN "
            "(SELECT edge_uid FROM connection_edges WHERE world_uid = ?)",
            [world_uid],
        )
        if not _in_transaction.get():
            await self._db.conn.commit()
