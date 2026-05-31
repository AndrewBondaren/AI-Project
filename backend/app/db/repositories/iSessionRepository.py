from abc import ABC, abstractmethod

from app.db.models.gameSession import GameSession
from app.db.models.sessionSummary import SessionSummary


class ISessionRepository(ABC):

    @abstractmethod
    async def get_all_enriched(self) -> list[SessionSummary]: ...

    @abstractmethod
    async def get_by_id(self, session_id: str) -> GameSession | None: ...

    @abstractmethod
    async def get_by_world_and_character(
        self, world_uid: str, character_id: str
    ) -> GameSession | None: ...

    @abstractmethod
    async def create(self, session: GameSession) -> None: ...

    @abstractmethod
    async def touch(self, session_id: str) -> None:
        """Обновить last_active_at до текущего времени."""
        ...

    # --- scene_participants ---

    @abstractmethod
    async def get_participants(self, session_id: str) -> list[str]:
        """Вернуть список character_uid активных участников сцены."""
        ...

    @abstractmethod
    async def add_participant(self, session_id: str, character_uid: str) -> None: ...

    @abstractmethod
    async def remove_participant(self, session_id: str, character_uid: str) -> None: ...

    @abstractmethod
    async def clear_participants(self, session_id: str) -> None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...
