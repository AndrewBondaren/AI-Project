"""Checked single-row/rowset IO; transaction policy belongs to the caller."""

from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.db.mapper import to_row, from_row
from app.application.publication.errors import PublicationInfrastructureError
from app.db.repositories.sqlite.shared.capabilities.scopeRegistry import SqliteScopeRegistry


class ScopedSqliteAccess:
    def __init__(self, registry: SqliteScopeRegistry) -> None:
        self.registry = registry

    async def one(self, scope: CommitReadScope | CommitScope, sql: str, values=()):
        conn = self.registry.check(scope)[3]
        async with conn.execute(sql, values) as cursor:
            self.registry.check(scope)
            row = await cursor.fetchone()
        return None if row is None else dict(row)

    async def all(self, scope: CommitReadScope | CommitScope, sql: str, values=()):
        conn = self.registry.check(scope)[3]
        async with conn.execute(sql, values) as cursor:
            self.registry.check(scope)
            return [dict(row) for row in await cursor.fetchall()]

    async def one_row[T](self, scope: CommitReadScope | CommitScope, model: type[T],
                         sql: str, values: tuple[object, ...] = ()) -> T | None:
        row = await self.one(scope, sql, values)
        if row is None:
            return None
        try:
            return from_row(model, row)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise PublicationInfrastructureError("invalid persisted row shape") from error

    async def all_rows[T](self, scope: CommitReadScope | CommitScope, model: type[T],
                          sql: str, values: tuple[object, ...] = ()) -> list[T]:
        rows = await self.all(scope, sql, values)
        try:
            return [from_row(model, row) for row in rows]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise PublicationInfrastructureError("invalid persisted row shape") from error

    async def insert(self, scope: CommitScope, row) -> None:
        conn = self.registry.check(scope, True)[3]
        names, values = to_row(row)
        async with conn.execute(
                f"INSERT INTO {row.__table__} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", values):
            self.registry.check(scope, True)
