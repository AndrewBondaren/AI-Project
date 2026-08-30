from collections.abc import Sequence

from app.db.bulkSql import executemany_rows
from app.db.database import Database, _in_transaction
from app.db.mapper import from_row, to_row
from app.db.models.namedLocation import NamedLocation
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.sqlite.base import BaseRepository


class SqliteNamedLocationRepository(BaseRepository[NamedLocation], INamedLocationRepository):

    def __init__(self, db: Database) -> None:
        super().__init__(db, NamedLocation)

    async def get_by_id(self, location_uid: str) -> NamedLocation | None:
        return await self.fetch_one("location_uid = ?", [location_uid])

    async def get_by_world(self, world_uid: str) -> list[NamedLocation]:
        return await self.fetch_all("world_uid = ?", [world_uid], order="display_name ASC")

    async def get_children(self, parent_uid: str) -> list[NamedLocation]:
        return await self.fetch_all("parent_location_uid = ?", [parent_uid], order="display_name ASC")

    async def list_descendants(self, ancestor_uid: str) -> list[NamedLocation]:
        sql = """
        WITH RECURSIVE tree(uid) AS (
          SELECT location_uid FROM named_locations WHERE location_uid = ?
          UNION ALL
          SELECT n.location_uid
            FROM named_locations n
            JOIN tree t ON n.parent_location_uid = t.uid
        )
        SELECT n.*
          FROM named_locations n
          JOIN tree t ON n.location_uid = t.uid
         WHERE n.location_uid != ?
         ORDER BY n.location_uid ASC
        """
        async with self._db.conn.execute(sql, [ancestor_uid, ancestor_uid]) as cur:
            rows = await cur.fetchall()
        return [from_row(NamedLocation, row) for row in rows]

    async def list_by_state_uids(
        self, world_uid: str, state_uids: Sequence[str],
    ) -> list[NamedLocation]:
        unique = [uid for uid in dict.fromkeys(state_uids) if uid]
        if not unique:
            return []
        placeholders = ", ".join("?" * len(unique))
        return await self.fetch_all(
            f"world_uid = ? AND state_uid IN ({placeholders})",
            [world_uid, *unique],
            order="location_uid ASC",
        )

    async def upsert_bulk(self, rows: Sequence[NamedLocation]) -> int:
        if not rows:
            return 0
        if _in_transaction.get():
            await self._replace_many(rows)
            return len(rows)
        async with self._db.transaction():
            await self._replace_many(rows)
        return len(rows)

    async def _replace_many(self, rows: Sequence[NamedLocation]) -> None:
        cols, _ = to_row(rows[0])
        placeholders = ", ".join("?" * len(cols))
        sql = (
            f"INSERT OR REPLACE INTO {self._table} ({', '.join(cols)}) "
            f"VALUES ({placeholders})"
        )
        await executemany_rows(self._db.conn, sql, rows)

    async def get_tree(self, world_uid: str) -> dict[str, int]:
        sql = """
        WITH RECURSIVE tree(uid, depth) AS (
          SELECT location_uid, 0
            FROM named_locations
           WHERE parent_location_uid IS NULL AND world_uid = ?
          UNION ALL
          SELECT n.location_uid, t.depth + 1
            FROM named_locations n
            JOIN tree t ON n.parent_location_uid = t.uid
        )
        SELECT uid, depth FROM tree
        """
        async with self._db.conn.execute(sql, [world_uid]) as cur:
            rows = await cur.fetchall()
        return {row[0]: row[1] for row in rows}

    async def get_faction_access_bulk(
        self, location_uids: list[str]
    ) -> dict[str, list[tuple[str, bool]]]:
        if not location_uids:
            return {}
        placeholders = ", ".join("?" * len(location_uids))
        sql = (
            f"SELECT location_uid, faction_uid, is_allowed "
            f"FROM location_faction_access "
            f"WHERE location_uid IN ({placeholders})"
        )
        async with self._db.conn.execute(sql, location_uids) as cur:
            rows = await cur.fetchall()
        result: dict[str, list[tuple[str, bool]]] = {uid: [] for uid in location_uids}
        for row in rows:
            result[row[0]].append((row[1], bool(row[2])))
        return result

    async def create(self, loc: NamedLocation) -> None:
        await self.insert(loc)

    async def update(self, loc: NamedLocation) -> None:
        await self.save(loc)

    async def upsert(self, loc: NamedLocation) -> None:
        await super().upsert(loc)

    async def delete(self, location_uid: str) -> None:
        await super().delete(location_uid)
