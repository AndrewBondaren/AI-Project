from abc import ABC, abstractmethod

from app.db.models.message import Turn, Message, NodeExecutionLog


class IMessageRepository(ABC):

    @abstractmethod
    async def create_turn(self, turn: Turn) -> None: ...

    @abstractmethod
    async def create_message(self, message: Message) -> None: ...

    @abstractmethod
    async def create_node_log(self, log: NodeExecutionLog) -> None: ...

    @abstractmethod
    async def get_turns_by_session(self, session_id: str, limit: int | None = None) -> list[Turn]:
        """Ходы сессии в хронологическом порядке. limit=None — вся история."""
        ...

    @abstractmethod
    async def get_messages_by_turn(self, turn_id: str) -> list[Message]:
        """LLM-сообщения хода в хронологическом порядке."""
        ...

    @abstractmethod
    async def get_history(self, session_id: str, limit: int | None = None) -> list[dict]:
        """История чата как [{role, text}] в хронологическом порядке. limit — количество ходов."""
        ...
