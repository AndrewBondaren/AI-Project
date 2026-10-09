"""Interface for global ``relief_templates`` library."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.models.reliefTemplate import ReliefTemplateRow


class IReliefTemplateRepository(ABC):

    @abstractmethod
    async def get_by_uid(self, template_uid: str) -> ReliefTemplateRow | None: ...

    @abstractmethod
    async def get_by_system_name(self, system_name: str) -> ReliefTemplateRow | None:
        """Transitional / deprecated until plan step 5b: ``system_name`` is no
        longer globally UNIQUE (tz_template_library_packs §3); raises on
        ambiguity instead of returning an arbitrary row. Callers migrate to
        template_uid or the effective catalog."""
        ...

    @abstractmethod
    async def list_all(self) -> list[ReliefTemplateRow]: ...

    @abstractmethod
    async def list_by_context(self, context: str) -> list[ReliefTemplateRow]: ...

    @abstractmethod
    async def upsert(self, row: ReliefTemplateRow) -> None: ...

    @abstractmethod
    async def delete(self, template_uid: str) -> None: ...
