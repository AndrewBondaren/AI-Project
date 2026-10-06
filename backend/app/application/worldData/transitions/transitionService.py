"""Application access to SQL transitions; validation/atomic writes belong to the repository."""

from collections.abc import Mapping
from typing import Any

from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.repositories.iTransitionRepository import ITransitionRepository


class TransitionService:
    def __init__(self, repo: ITransitionRepository, registry: WorldTransitionTypeRegistry):
        self._repo = repo
        self._registry = registry

    async def create(self, transition: Transition) -> Transition:
        return await self._repo.create(transition)

    async def read(self, uid: str) -> Transition | None:
        return await self._repo.get(uid)

    async def update(self, uid: str, patch: Mapping[str, Any]) -> Transition:
        return await self._repo.update(uid, patch)

    async def delete(self, uid: str) -> bool:
        return await self._repo.delete(uid)

    async def entries_of(self, world_uid: str, location_uid: str) -> list[Transition]:
        transitions = await self._repo.owned_by_destination(world_uid, location_uid)
        entries = []
        for item in transitions:
            self._registry.require(item.system_transition_type)
            if self._registry.type_for(item.system_transition_type).entry:
                entries.append(item)
        return entries

    async def for_level(self, world_uid: str, level_uid: str) -> list[Transition]:
        return await self._repo.touching_level(world_uid, level_uid)

    async def for_node(self, world_uid: str, node_uid: str) -> list[Transition]:
        return await self._repo.touching_node(world_uid, node_uid)
