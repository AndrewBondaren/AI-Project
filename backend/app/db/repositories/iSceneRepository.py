from abc import ABC, abstractmethod

from app.db.models.sessionScene import SessionScene


class ISceneRepository(ABC):

    @abstractmethod
    async def get(self, session_id: str) -> SessionScene | None: ...

    @abstractmethod
    async def upsert(self, scene: SessionScene) -> None: ...
