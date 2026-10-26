"""Interface for global ``relief_templates`` library."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.models.reliefTemplate import ReliefTemplateRow


class IReliefTemplateRepository(ABC):

    async def insert(self, row: ReliefTemplateRow) -> None:
        raise NotImplementedError

    async def save(self, row: ReliefTemplateRow) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_uid(self, template_uid: str) -> ReliefTemplateRow | None: ...

    @abstractmethod
    async def list_all(self) -> list[ReliefTemplateRow]: ...

    @abstractmethod
    async def list_by_context(self, context: str) -> list[ReliefTemplateRow]: ...

    @abstractmethod
    async def upsert(self, row: ReliefTemplateRow) -> None: ...

    @abstractmethod
    async def delete(self, template_uid: str) -> None: ...
