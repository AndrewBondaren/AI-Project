"""Opaque token; only the issuing registry grants authority."""

from typing import TYPE_CHECKING

from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope

if TYPE_CHECKING:
    from app.db.repositories.sqlite.shared.capabilities.scopeRegistry import SqliteScopeRegistry


class SqliteCommitScopeBinding(CommitScope, CommitReadScope):
    __slots__ = ("_registry", "_read_scope")

    def __init__(self, registry: "SqliteScopeRegistry") -> None:
        self._registry = registry
        self._read_scope: CommitReadScope | None = None

    def assert_active(self) -> None:
        self._registry.check(self)

    @property
    def read_scope(self) -> CommitReadScope:
        self.assert_active()
        if self._read_scope is None:
            self._read_scope = self._registry.read_only(self)
        return self._read_scope
