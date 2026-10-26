"""Aggregate SQL repository contract; caller supplies world registry/reference snapshots."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationLevel import LocationLevel
from app.db.models.namedLocation import NamedLocation


@dataclass(frozen=True)
class TransitionRepositoryContext:
    world_uid: str
    registry: WorldTransitionTypeRegistry
    levels: Mapping[str, LocationLevel]
    locations: Mapping[str, NamedLocation]
    nodes: Mapping[str, ConnectionNode]


class ITransitionRepository(ABC):
    @abstractmethod
    async def get(self, uid: str) -> Transition | None: ...

    @abstractmethod
    async def create(self, transition: Transition) -> Transition: ...

    @abstractmethod
    async def update(self, uid: str, patch: Mapping[str, Any]) -> Transition: ...

    @abstractmethod
    async def delete(self, uid: str) -> bool: ...

    @abstractmethod
    async def upsert_bulk(self, transitions: Sequence[Transition]) -> int: ...

    @abstractmethod
    async def owned_by_destination(self, world_uid: str, location_uid: str) -> list[Transition]: ...

    @abstractmethod
    async def touching_level(self, world_uid: str, level_uid: str) -> list[Transition]: ...

    @abstractmethod
    async def touching_node(self, world_uid: str, node_uid: str) -> list[Transition]: ...
