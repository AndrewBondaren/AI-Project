"""Nominal runtime capabilities. Only a storage adapter can implement ownership guards."""

from abc import ABC, abstractmethod
from typing import Protocol


class CommitReadScope(ABC):
    __slots__ = ()

    @abstractmethod
    def assert_active(self) -> None:
        """Check task, database, lifetime and read capability before each access."""


class CommitScope(ABC):
    __slots__ = ()

    @property
    @abstractmethod
    def read_scope(self) -> CommitReadScope:
        """Read capability of this same transaction, without write authority."""

    @abstractmethod
    def assert_active(self) -> None:
        """Check task, database, lifetime and write capability before each access."""


class IDomainCommitBinding[S](Protocol):
    def bind(self, scope: CommitScope) -> S:
        """Bind domain storage without exposing connection or transaction controls."""
        ...
