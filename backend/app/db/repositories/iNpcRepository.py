from abc import ABC, abstractmethod

from app.db.models.npc import Npc


class INpcRepository(ABC):

    @abstractmethod
    async def get_by_id(self, character_uid: str) -> Npc | None: ...

    @abstractmethod
    async def get_by_world(self, world_uid: str) -> list[Npc]: ...

    @abstractmethod
    async def get_by_location(self, world_uid: str, location: str) -> list[Npc]: ...

    @abstractmethod
    async def create(self, npc: Npc) -> None: ...

    @abstractmethod
    async def update(self, npc: Npc) -> None: ...

    @abstractmethod
    async def convert_from_player(self, character_uid: str, world_uid: str) -> None:
        """Конвертировать player -> npc: меняет character_type и привязывает к миру."""
        ...

    @abstractmethod
    async def clear_scene_state(self, character_uid: str) -> None:
        """Очистить system_current_target и system_current_thoughts при выходе из сцены."""
        ...
