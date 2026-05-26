from abc import ABC, abstractmethod

from app.db.models.sessionPending import SessionPending


class IPendingRepository(ABC):

    @abstractmethod
    async def upsert(self, session_id: str, player_input: str) -> None: ...

    @abstractmethod
    async def update_snapshot(self, session_id: str, snapshot_json: str) -> None: ...

    @abstractmethod
    async def get(self, session_id: str) -> SessionPending | None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    @abstractmethod
    async def cleanup_stale(self) -> None:
        """Удаляет устаревшие pending-записи где turns уже содержит тот же player_input."""
        ...
