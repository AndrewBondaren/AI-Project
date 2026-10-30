"""SQLite-owned transaction capabilities and checked DB boundary primitives."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Annotated

import aiosqlite
from pydantic import Field, StrictInt, TypeAdapter

from app.application.publication.errors import PublicationInfrastructureError, UnknownCommitOutcome
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.application.encoding.canonicalCodec import content_digest
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.db.database import Database
from app.db.guardedConnection import GuardedConnection
from app.db.mapper import to_row

_UID = TypeAdapter(EntityUid)
_HASH = TypeAdapter(RevisionHex)
_POS = TypeAdapter(Annotated[StrictInt, Field(ge=1)])


class SqliteCommitScopeBinding(CommitScope, CommitReadScope):
    __slots__ = ("_store",)

    def __init__(self, store: "SqlitePublicationCommitStore") -> None:
        self._store = store

    def assert_active(self) -> None:
        self._store._check(self)

    @property
    def read_scope(self) -> CommitReadScope:
        self.assert_active()
        return self._store._issue(False, self._store._check(self)[2])


class SqlitePublicationCommitStore:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._issued: dict[SqliteCommitScopeBinding, tuple[asyncio.Task, bool, EntityUid | None, GuardedConnection]] = {}
        self._broken = False

    def _issue(self, write: bool, operation_id: EntityUid | None) -> SqliteCommitScopeBinding:
        task = asyncio.current_task()
        conn = self._db.main_conn
        if task is None or not isinstance(conn, GuardedConnection) or not conn.owns_unit_of_work:
            raise PublicationInfrastructureError("capability requires this task's GuardedConnection UOW")
        scope = SqliteCommitScopeBinding(self)
        self._issued[scope] = (task, write, operation_id, conn)
        return scope

    def _check(self, scope: CommitReadScope | CommitScope, write: bool = False):
        if self._broken:
            raise UnknownCommitOutcome("connection quarantined; recover through a fresh confirmed connection")
        if not isinstance(scope, SqliteCommitScopeBinding) or scope not in self._issued:
            raise PublicationInfrastructureError("unissued, expired or foreign database scope")
        entry = self._issued[scope]
        if (entry[0] is not asyncio.current_task() or entry[3] is not self._db.main_conn
                or not entry[3].owns_unit_of_work or (write and not entry[1])):
            raise PublicationInfrastructureError("scope task/database/lifetime/read-write mismatch")
        return entry

    async def _settle(self, conn: GuardedConnection, sql: str | None) -> bool:
        # The owner still holds unit_of_work. Queue through the existing driver
        # worker without asking a shield child task to reacquire the owner's gate.
        function = conn._conn.close if sql is None else conn._conn.execute
        arguments = () if sql is None else (sql,)
        pending = asyncio.create_task(aiosqlite.Connection._execute(conn, function, *arguments))
        cancelled = False
        while not pending.done():
            try:
                await asyncio.shield(pending)
            except asyncio.CancelledError:
                cancelled = True
        pending.result()  # Worker acknowledgement; an error here is not rollback proof.
        return cancelled

    async def _quarantine(self, conn: GuardedConnection) -> None:
        self._broken = True
        try:
            await self._settle(conn, None)
        finally:
            # Physical close has drained queued work before driver shutdown.
            try:
                await conn.close()
            except BaseException:
                pass

    @asynccontextmanager
    async def _transaction(self, operation_id: EntityUid | None, write: bool) -> AsyncIterator[SqliteCommitScopeBinding]:
        if self._broken:
            raise UnknownCommitOutcome("connection requires recovery")
        conn = self._db.main_conn
        if not isinstance(conn, GuardedConnection):
            raise PublicationInfrastructureError("expected the existing GuardedConnection")
        if conn.owns_unit_of_work:
            raise PublicationInfrastructureError("nested/ambient publication transaction is forbidden")
        async with conn.unit_of_work():
            issued = set(self._issued)
            try:
                try:
                    await conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                    scope = self._issue(write, operation_id)
                    yield scope
                except BaseException:
                    try:
                        if conn.in_transaction:
                            await self._settle(conn, "ROLLBACK")
                    except BaseException as rollback_error:
                        await self._quarantine(conn)
                        raise UnknownCommitOutcome("rollback could not be confirmed") from rollback_error
                    raise
                else:
                    try:
                        cancelled = await self._settle(conn, "COMMIT" if write else "ROLLBACK")
                    except BaseException as commit_error:
                        await self._quarantine(conn)
                        raise UnknownCommitOutcome("publication outcome must be recovered") from commit_error
                    if cancelled:
                        # COMMIT/ROLLBACK is acknowledged; cancellation is never a refusal.
                        raise asyncio.CancelledError
            finally:
                for capability in set(self._issued) - issued:
                    del self._issued[capability]

    def transaction(self, operation_id: EntityUid):
        operation_id = _UID.validate_python(operation_id, strict=True)
        return self._transaction(operation_id, True)

    def _read(self):
        return self._transaction(None, False)


@asynccontextmanager
async def _read_scope(store: SqlitePublicationCommitStore, scope: CommitReadScope | None):
    if scope is not None:
        store._check(scope)
        yield scope
    else:
        async with store._read() as pinned:
            yield pinned.read_scope


async def _one(store: SqlitePublicationCommitStore, scope: CommitReadScope | CommitScope, sql: str, values=()):
    conn = store._check(scope)[3]
    async with conn.execute(sql, values) as cursor:
        store._check(scope)
        row = await cursor.fetchone()
    return None if row is None else dict(row)


async def _all(store: SqlitePublicationCommitStore, scope: CommitReadScope | CommitScope, sql: str, values=()):
    conn = store._check(scope)[3]
    async with conn.execute(sql, values) as cursor:
        store._check(scope)
        return [dict(row) for row in await cursor.fetchall()]


async def _insert(store: SqlitePublicationCommitStore, scope: CommitScope, row) -> None:
    conn = store._check(scope, True)[3]
    names, values = to_row(row)
    async with conn.execute(f"INSERT INTO {row.__table__} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})", values):
        store._check(scope, True)


def _write_operation(store: SqlitePublicationCommitStore, scope: CommitScope) -> EntityUid:
    value = store._check(scope, True)[2]
    if value is None:
        raise PublicationInfrastructureError("write capability requires an operation identity")
    return _UID.validate_python(value, strict=True)


def _fields(row: Mapping, *, uids=(), optional_uids=(), positives=(), hashes=(), optional_hashes=(), booleans=()) -> None:
    try:
        for key in uids:
            _UID.validate_python(row[key], strict=True)
        for key in optional_uids:
            if row[key] is not None:
                _UID.validate_python(row[key], strict=True)
        for key in positives:
            _POS.validate_python(row[key], strict=True)
        for key in hashes:
            _HASH.validate_python(row[key], strict=True)
        for key in optional_hashes:
            if row[key] is not None:
                _HASH.validate_python(row[key], strict=True)
        for key in booleans:
            if type(row[key]) is not int or row[key] not in (0, 1):
                raise ValueError("raw SQL boolean must be integer 0/1")
    except (ValueError, TypeError, KeyError) as error:
        raise PublicationInfrastructureError("invalid persisted scalar") from error


def _wire[E: StrEnum](kind: type[E], value: object) -> E:
    if type(value) is not str:
        raise PublicationInfrastructureError("SQL enum must be a wire string")
    try:
        return kind(value)
    except ValueError as error:
        raise PublicationInfrastructureError("unknown stored enum") from error


def _checked_blob(data: bytes, checksum: RevisionHex) -> bytes:
    _HASH.validate_python(checksum, strict=True)
    if type(data) is not bytes or content_digest(data).hex() != checksum:
        raise PublicationInfrastructureError("stored bytes/checksum mismatch")
    return data
