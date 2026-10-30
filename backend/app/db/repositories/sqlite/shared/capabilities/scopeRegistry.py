"""Issued authority, ownership, lifetime and logical quarantine; no SQL."""

import asyncio

from app.application.publication.errors import PublicationInfrastructureError, UnknownCommitOutcome
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.identity.uid import EntityUid
from app.db.database import Database
from app.db.guardedConnection import GuardedConnection
from app.db.repositories.sqlite.shared.capabilities.scopeBinding import SqliteCommitScopeBinding
from app.db.repositories.sqlite.shared.validation.rowValues import _UID


class SqliteScopeRegistry:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._issued: dict[SqliteCommitScopeBinding, tuple[asyncio.Task, bool, EntityUid | None, GuardedConnection]] = {}
        self._broken = False

    def assert_database(self, db: Database) -> None:
        if db is not self._db:
            raise ValueError("registry must share the coordinator's Database")

    def assert_available(self) -> None:
        if self._broken:
            raise UnknownCommitOutcome("connection quarantined; recover through a fresh confirmed connection")

    def quarantine(self) -> None:
        self._broken = True

    def issue(self, write: bool, operation_id: EntityUid | None) -> SqliteCommitScopeBinding:
        self.assert_available()
        task = asyncio.current_task()
        conn = self._db.main_conn
        if task is None or not isinstance(conn, GuardedConnection) or not conn.owns_unit_of_work:
            raise PublicationInfrastructureError("capability requires this task's GuardedConnection UOW")
        if operation_id is not None:
            operation_id = _UID.validate_python(operation_id, strict=True)
        scope = SqliteCommitScopeBinding(self)
        self._issued[scope] = (task, write, operation_id, conn)
        return scope

    def check(self, scope: CommitReadScope | CommitScope, write: bool = False):
        self.assert_available()
        if not isinstance(scope, SqliteCommitScopeBinding) or scope not in self._issued:
            raise PublicationInfrastructureError("unissued, expired or foreign database scope")
        entry = self._issued[scope]
        if (entry[0] is not asyncio.current_task() or entry[3] is not self._db.main_conn
                or not entry[3].owns_unit_of_work or (write and not entry[1])):
            raise PublicationInfrastructureError("scope task/database/lifetime/read-write mismatch")
        return entry

    def read_only(self, scope: CommitReadScope | CommitScope) -> CommitReadScope:
        return self.issue(False, self.check(scope)[2])

    def operation_id(self, scope: CommitScope) -> EntityUid:
        value = self.check(scope, True)[2]
        if value is None:
            raise PublicationInfrastructureError("write capability requires an operation identity")
        return _UID.validate_python(value, strict=True)

    def revoke(self) -> None:
        # One UOW per connection; revoke only the exiting owner and its derived tokens.
        task = asyncio.current_task()
        for scope, entry in tuple(self._issued.items()):
            if entry[0] is task:
                del self._issued[scope]
