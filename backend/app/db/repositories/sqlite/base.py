from typing import Any, Generic, Type, TypeVar

from app.db.database import Database, _in_transaction
from app.db.mapper import from_row, pk_col, to_row, to_update_row

T = TypeVar("T")


class BaseRepository(Generic[T]):

    def __init__(self, db: Database, model_cls: Type[T]) -> None:
        self._db = db
        self._cls = model_cls
        self._table: str = model_cls.__table__
        self._pk_col: str = pk_col(model_cls)
        disc: dict = getattr(model_cls, "__discriminator__", {})
        self._disc_where: str = " AND ".join(f"{c} = ?" for c in disc)
        self._disc_vals: list[Any] = list(disc.values())

    async def insert(self, obj: T) -> None:
        cols, vals = to_row(obj)
        placeholders = ", ".join("?" * len(cols))
        sql = f"INSERT INTO {self._table} ({', '.join(cols)}) VALUES ({placeholders})"
        await self._db.conn.execute(sql, vals)
        if not _in_transaction.get():
            await self._db.conn.commit()

    async def save(self, obj: T) -> None:
        set_clauses, set_vals, pk_val = to_update_row(obj)
        where = f"{self._pk_col} = ?"
        if self._disc_where:
            where += f" AND {self._disc_where}"
        sql = f"UPDATE {self._table} SET {', '.join(set_clauses)} WHERE {where}"
        await self._db.conn.execute(sql, [*set_vals, pk_val, *self._disc_vals])
        if not _in_transaction.get():
            await self._db.conn.commit()

    async def upsert(self, obj: T) -> None:
        cols, vals = to_row(obj)
        placeholders = ", ".join("?" * len(cols))
        sql = f"INSERT OR REPLACE INTO {self._table} ({', '.join(cols)}) VALUES ({placeholders})"
        await self._db.conn.execute(sql, vals)
        if not _in_transaction.get():
            await self._db.conn.commit()

    async def delete(self, pk_val: Any) -> None:
        where = f"{self._pk_col} = ?"
        params: list[Any] = [pk_val]
        if self._disc_where:
            where += f" AND {self._disc_where}"
            params.extend(self._disc_vals)
        sql = f"DELETE FROM {self._table} WHERE {where}"
        await self._db.conn.execute(sql, params)
        if not _in_transaction.get():
            await self._db.conn.commit()

    async def fetch_one(self, where: str, params: list[Any]) -> T | None:
        sql, full_params = self._build_select(where, params)
        async with self._db.conn.execute(sql, full_params) as cur:
            row = await cur.fetchone()
        return from_row(self._cls, row) if row else None

    async def fetch_all(
        self,
        where: str = "",
        params: list[Any] | None = None,
        order: str = "",
    ) -> list[T]:
        sql, full_params = self._build_select(where, params or [])
        if order:
            sql += f" ORDER BY {order}"
        async with self._db.conn.execute(sql, full_params) as cur:
            rows = await cur.fetchall()
        return [from_row(self._cls, r) for r in rows]

    def _build_select(self, where: str, params: list[Any]) -> tuple[str, list[Any]]:
        parts: list[str] = []
        full_params: list[Any] = []
        if self._disc_where:
            parts.append(self._disc_where)
            full_params.extend(self._disc_vals)
        if where:
            parts.append(where)
            full_params.extend(params)
        sql = f"SELECT * FROM {self._table}"
        if parts:
            sql += f" WHERE {' AND '.join(parts)}"
        return sql, full_params
