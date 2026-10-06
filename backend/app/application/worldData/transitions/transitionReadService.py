"""Combined SQL and explicit building-pack reads; no movement or discovery policy."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.read.settlementStructureIndex import transitions_for_level
from app.application.worldData.transitions.transitionService import TransitionService
from app.application.worldData.transitions.transitionValidation import validate_transitions
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.worldPack.settlementStructureWire import BuildingShellWire
from app.db.repositories.iTransitionRepository import TransitionRepositoryContext


@dataclass(frozen=True)
class BuildingTransitionPackBinding:
    """Caller-provided routing scope; no hierarchy or area NL is inferred."""
    settlement_uid: str
    building_uid: str
    level_uids: frozenset[str]
    owner_location_uids: frozenset[str]


class TransitionReadService:
    def __init__(self, sql: TransitionService, reader: WorldPackReader,
                 context: TransitionRepositoryContext, bindings: Sequence[BuildingTransitionPackBinding]):
        self._sql = sql
        self._reader = reader
        self._context = context
        self._bindings = tuple(bindings)

    def _check_world(self, world_uid: str) -> None:
        if world_uid != self._context.world_uid:
            raise ValueError("transition reader belongs to another world")

    def _building(self, binding: BuildingTransitionPackBinding) -> BuildingShellWire:
        building = self._reader.read_building_interior_transitions(
            binding.settlement_uid, binding.building_uid, registry=self._context.registry)
        block = building.interior_transitions
        if block.world_uid != self._context.world_uid:
            raise ValueError("building pack belongs to another world")
        if not binding.level_uids <= set(block.level_uids):
            raise ValueError("pack binding contains levels absent from building pack")
        validate_transitions(self._context.world_uid, block.transitions, levels=self._context.levels,
            locations=self._context.locations, nodes=self._context.nodes, registry=self._context.registry)
        return building

    async def _merge(self, sql: Sequence[Transition], packed: Sequence[Transition]) -> list[Transition]:
        # SQL wins UID collisions so current CRUD/runtime state reaches consumers.
        by_uid = {item.transition_uid: item for item in sql}
        for item in packed:
            if item.transition_uid not in by_uid:
                # An edited SQL aggregate may no longer match the original query.
                by_uid[item.transition_uid] = await self._sql.read(item.transition_uid) or item
        return list(by_uid.values())

    async def for_level(self, world_uid: str, level_uid: str) -> list[Transition]:
        self._check_world(world_uid)
        sql = await self._sql.for_level(world_uid, level_uid)
        packed = []
        for binding in self._bindings:
            if level_uid in binding.level_uids:
                packed.extend(transitions_for_level(self._building(binding), level_uid))
        return [item for item in await self._merge(sql, packed)
                if item.source.level_uid == level_uid or item.destination.level_uid == level_uid]

    async def entries_of(self, world_uid: str, location_uid: str) -> list[Transition]:
        self._check_world(world_uid)
        sql = await self._sql.entries_of(world_uid, location_uid)
        packed = []
        for binding in self._bindings:
            if location_uid in binding.owner_location_uids:
                for item in self._building(binding).interior_transitions.transitions:
                    if (item.destination_side.owner_location_uid == location_uid
                            and self._context.registry.type_for(item.system_transition_type).entry):
                        packed.append(item)
        return [item for item in await self._merge(sql, packed)
                if item.destination_side.owner_location_uid == location_uid
                and self._context.registry.type_for(item.system_transition_type).entry]
