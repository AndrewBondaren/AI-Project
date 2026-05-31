from abc import ABC, abstractmethod

from app.db.models.state import State


class IStateRepository(ABC):

    @abstractmethod
    async def get_by_id(self, state_uid: str) -> State | None: ...

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[State]: ...

    @abstractmethod
    async def get_by_uids(self, uids: list[str]) -> list[State]: ...

    @abstractmethod
    async def upsert(self, state: State) -> None: ...

    @abstractmethod
    async def delete(self, state_uid: str) -> None: ...
