"""Task-local artifact scope joins; SQL and transaction lifecycle stay with owners."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import cast

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.identity.uid import EntityUid
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.validation.rowValues import _UID
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.ids.deterministicIds import runtime_uid


class SqliteArtifactScope:
    def __init__(self, commits: SqlitePublicationCommitStore, access: ScopedSqliteAccess) -> None:
        if access.registry is not commits.registry:
            raise ValueError("artifact scope must share the coordinator's registry")
        self._commits, self._access = commits, access
        self._binding: ContextVar[CommitScope | CommitReadScope | None] = ContextVar(
            "artifact_scope", default=None)

    @property
    def commits(self) -> SqlitePublicationCommitStore:
        return self._commits

    @property
    def access(self) -> ScopedSqliteAccess:
        return self._access

    def _require_unbound(self) -> None:
        current = self._binding.get()
        if current is not None:
            self._commits.registry.check(current)
            raise PublicationInfrastructureError("artifact guard/bind is not reentrant")

    @asynccontextmanager
    async def bind(self, scope: CommitScope) -> AsyncIterator[None]:
        """Borrow an explicit publication capability without ending its transaction."""
        self._commits.registry.check(scope, True)
        self._require_unbound()
        token = self._binding.set(scope)
        try:
            yield
        finally:
            self._binding.reset(token)

    @asynccontextmanager
    async def transaction(self, operation_id: EntityUid) -> AsyncIterator[CommitScope]:
        operation_id = _UID.validate_python(operation_id, strict=True)
        current = self._binding.get()
        if current is not None:
            self._commits.registry.check(current, True)
            yield cast(CommitScope, current)
        else:
            async with self._commits.transaction(operation_id) as scope:
                async with self.bind(scope):
                    yield scope

    @asynccontextmanager
    async def read_scope(self) -> AsyncIterator[CommitReadScope]:
        current = self._binding.get()
        if current is not None:
            self._commits.registry.check(current)
            yield self._commits.registry.read_only(current)
        else:
            async with self._commits.read_scope() as scope:
                token = self._binding.set(scope)
                try:
                    yield scope
                finally:
                    self._binding.reset(token)

    @asynccontextmanager
    async def guard(self, ref: ArtifactRef) -> AsyncIterator[None]:
        """Hold the database writer coordinator across the caller's physical IO."""
        ArtifactRef.model_validate(ref, strict=True)
        self._require_unbound()
        async with self.transaction(runtime_uid()):
            yield
