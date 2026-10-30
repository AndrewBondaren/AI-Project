"""Publication transaction lifecycle; mechanisms live in shared SQLite owners."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, AbstractAsyncContextManager

from app.application.publication.errors import PublicationInfrastructureError, UnknownCommitOutcome
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.identity.uid import EntityUid
from app.db.database import Database
from app.db.guardedConnection import GuardedConnection
from app.db.repositories.sqlite.shared.capabilities.scopeRegistry import SqliteScopeRegistry
from app.db.repositories.sqlite.shared.transactions.transactionDriver import SqliteTransactionDriver
from app.db.repositories.sqlite.shared.validation.rowValues import _UID


class SqlitePublicationCommitStore:
    def __init__(self, db: Database, registry: SqliteScopeRegistry, driver: SqliteTransactionDriver) -> None:
        registry.assert_database(db)
        self._db, self.registry, self.driver = db, registry, driver

    async def _quarantine(self, conn: GuardedConnection) -> None:
        self.registry.quarantine()
        try:
            await self.driver.close(conn)
        except BaseException:
            # A failed close cannot change the unknown transaction outcome.
            pass

    @asynccontextmanager
    async def _transaction(self, operation_id: EntityUid | None, write: bool) -> AsyncIterator[CommitScope]:
        self.registry.assert_available()
        conn = self._db.main_conn
        if not isinstance(conn, GuardedConnection):
            raise PublicationInfrastructureError("expected the existing GuardedConnection")
        if conn.owns_unit_of_work:
            raise PublicationInfrastructureError("nested/ambient publication transaction is forbidden")
        async with conn.unit_of_work():
            # A queued caller must recheck quarantine after acquiring the gate.
            self.registry.assert_available()
            if conn is not self._db.main_conn:
                raise PublicationInfrastructureError("database connection changed while waiting")
            try:
                try:
                    await self.driver.begin(conn, write=write)
                    yield self.registry.issue(write, operation_id)
                except BaseException:
                    cancelled = False
                    try:
                        if conn.in_transaction:
                            cancelled = await self.driver.rollback(conn)
                    except BaseException as rollback_error:
                        await self._quarantine(conn)
                        raise UnknownCommitOutcome("rollback could not be confirmed") from rollback_error
                    if cancelled:
                        raise asyncio.CancelledError
                    raise
                else:
                    try:
                        cancelled = await (self.driver.commit(conn) if write else self.driver.rollback(conn))
                    except BaseException as commit_error:
                        await self._quarantine(conn)
                        raise UnknownCommitOutcome("publication outcome must be recovered") from commit_error
                    if cancelled:
                        raise asyncio.CancelledError
            finally:
                self.registry.revoke()

    def transaction(self, operation_id: EntityUid) -> AbstractAsyncContextManager[CommitScope]:
        operation_id = _UID.validate_python(operation_id, strict=True)
        return self._transaction(operation_id, True)

    @asynccontextmanager
    async def read_scope(self, existing_scope: CommitReadScope | None = None) -> AsyncIterator[CommitReadScope]:
        if existing_scope is not None:
            self.registry.check(existing_scope)
            yield existing_scope
        else:
            async with self._transaction(None, False) as scope:
                yield scope.read_scope
