from abc import ABC, abstractmethod

from app.db.models.message import Message


class IMessageRepository(ABC):

    @abstractmethod
    async def create(self, message: Message) -> None: ...

    @abstractmethod
    async def get_by_session(self, session_id: str, limit: int | None = None) -> list[Message]:
        """Сообщения сессии в хронологическом порядке. limit=None — вся история."""
        ...
