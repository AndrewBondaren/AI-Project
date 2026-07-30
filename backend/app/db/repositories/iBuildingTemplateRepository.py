from abc import ABC, abstractmethod

from app.db.models.buildingTemplate import BuildingTemplateRow


class IBuildingTemplateRepository(ABC):

    @abstractmethod
    async def get_by_uid(self, template_uid: str) -> BuildingTemplateRow | None: ...

    @abstractmethod
    async def list_all(self) -> list[BuildingTemplateRow]: ...

    @abstractmethod
    async def upsert(self, row: BuildingTemplateRow) -> None: ...

    @abstractmethod
    async def delete(self, template_uid: str) -> None: ...
