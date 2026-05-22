from abc import ABC, abstractmethod

from app.db.models.player import Player


class IPlayerRepository(ABC):

    @abstractmethod
    async def get_by_id(self, character_uid: str) -> Player | None: ...

    @abstractmethod
    async def get_all(self) -> list[Player]: ...

    @abstractmethod
    async def create(self, player: Player) -> None: ...

    @abstractmethod
    async def update(self, player: Player) -> None: ...
