"""Interface for global ``structure_templates`` library (5o split)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.models.structureTemplate import StructureTemplateRow


class IStructureTemplateRepository(ABC):

    @abstractmethod
    async def get_by_uid(self, template_uid: str) -> StructureTemplateRow | None: ...

    @abstractmethod
    async def list_all(self) -> list[StructureTemplateRow]: ...

    @abstractmethod
    async def upsert(self, row: StructureTemplateRow) -> None: ...

    @abstractmethod
    async def delete(self, template_uid: str) -> None: ...
