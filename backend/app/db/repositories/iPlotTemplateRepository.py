"""UID-addressed plot body storage; validation/policy belong to the library."""

from abc import ABC, abstractmethod

from app.db.models.plotTemplate import PlotTemplateRow


class IPlotTemplateRepository(ABC):
    @abstractmethod
    async def insert(self, row: PlotTemplateRow) -> None: ...

    @abstractmethod
    async def save(self, row: PlotTemplateRow) -> None: ...

    @abstractmethod
    async def get_by_uid(self, template_uid: str) -> PlotTemplateRow | None: ...

    @abstractmethod
    async def list_all(self) -> list[PlotTemplateRow]: ...

    @abstractmethod
    async def delete(self, template_uid: str) -> None: ...
