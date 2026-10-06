"""Pure projection of final Transition aggregates into SQL and building pack blocks."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.application.worldData.transitions.transitionStoragePolicy import (
    BuildingTransitionScope, partition_transitions,
)
from app.application.worldData.transitions.transitionValidation import validate_transitions
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.dataModel.worldPack.settlementStructureWire import BuildingInteriorTransitionsWire
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationLevel import LocationLevel
from app.db.models.namedLocation import NamedLocation


@dataclass(frozen=True)
class SettlementTransitionProjection:
    sql_transitions: list[Transition]
    pack_by_building: dict[str, BuildingInteriorTransitionsWire]


def project_settlement_transitions(
    world_uid: str, transitions: Sequence[Transition], *,
    levels: Mapping[str, LocationLevel], locations: Mapping[str, NamedLocation],
    nodes: Mapping[str, ConnectionNode], building_scopes: Sequence[BuildingTransitionScope],
    registry: WorldTransitionTypeRegistry,
) -> SettlementTransitionProjection:
    """Use finalized UIDs/geometry. No rebinding, hierarchy inference, state reset or I/O.

    Each supplied building layout requires a main entrance owned by its destination
    side. Overrides remain nullable data: consumers perform owner inheritance.
    """
    validate_transitions(world_uid, transitions, levels=levels, locations=locations, nodes=nodes, registry=registry)
    uids = {item.transition_uid for item in transitions}
    if len(uids) != len(transitions):
        raise ValueError("duplicate transition UID in settlement projection")
    main_owners = {
        item.destination_side.owner_location_uid for item in transitions
        if registry.type_for(item.system_transition_type) == TransitionType.MAIN_ENTRANCE
    }
    for scope in building_scopes:
        building = locations.get(scope.building_uid)
        if building is None or building.location_uid != scope.building_uid or building.world_uid != world_uid:
            raise ValueError(f"unknown building scope {scope.building_uid!r} in world {world_uid!r}")
        if scope.transition_uids - uids:
            raise ValueError(f"building {scope.building_uid!r} scope contains missing transitions")
        for uid in scope.level_uids:
            level = levels.get(uid)
            owner = locations.get(level.location_uid) if level is not None else None
            if (level is None or level.level_uid != uid or owner is None
                    or owner.location_uid != level.location_uid or owner.world_uid != world_uid):
                raise ValueError(f"building {scope.building_uid!r} scope contains unknown level {uid!r}")
        if scope.building_uid not in main_owners:
            raise ValueError(f"building {scope.building_uid!r} has no MAIN_ENTRANCE destination owner")
    partition = partition_transitions(transitions, building_scopes=building_scopes, registry=registry)
    packed = {}
    for scope in building_scopes:
        packed[scope.building_uid] = BuildingInteriorTransitionsWire.model_validate({
            "format": "building-interior-transitions-v1", "world_uid": world_uid,
            "level_uids": sorted(scope.level_uids),
            "transitions": [item.model_dump(mode="json") for item in partition.pack_by_building.get(scope.building_uid, ())],
        }, context={"transition_type_registry": registry})
    return SettlementTransitionProjection(list(partition.sql_transitions), packed)
