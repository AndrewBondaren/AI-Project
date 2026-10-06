"""Pure SQL/pack partition using explicit materialized building layout scopes."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionSpace
from app.dataModel.locations.transitions.transitionOrigin import TransitionOrigin
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry


@dataclass(frozen=True)
class BuildingTransitionScope:
    """Caller declares which transitions and levels its materialized layout contains."""

    building_uid: str
    level_uids: frozenset[str]
    transition_uids: frozenset[str]


@dataclass(frozen=True)
class TransitionPartition:
    sql_transitions: tuple[Transition, ...]
    pack_by_building: dict[str, tuple[Transition, ...]]


def partition_transitions(
    transitions: Sequence[Transition],
    *,
    building_scopes: Sequence[BuildingTransitionScope],
    registry: WorldTransitionTypeRegistry,
) -> TransitionPartition:
    """Call after validate_transitions. No ownership, parent or overlap inference."""
    scopes: dict[str, BuildingTransitionScope] = {}
    by_transition: dict[str, BuildingTransitionScope] = {}
    for scope in building_scopes:
        if scope.building_uid in scopes:
            raise ValueError(f"duplicate building scope {scope.building_uid!r}")
        scopes[scope.building_uid] = scope
        for uid in scope.transition_uids:
            if uid in by_transition:
                raise ValueError(f"transition {uid!r} belongs to multiple building scopes")
            by_transition[uid] = scope
    sql: list[Transition] = []
    packed: dict[str, list[Transition]] = {}
    for transition in transitions:
        entry = registry.entry_for(transition.system_transition_type)
        if entry is None:
            raise ValueError(f"unknown transition type {transition.system_transition_type!r}")
        scope = by_transition.get(transition.transition_uid)
        interior = (
            scope is not None
            and transition.source.space == TransitionSpace.LEVEL
            and transition.destination.space == TransitionSpace.LEVEL
            and transition.source.geometry is not None
            and transition.destination.geometry is not None
            and transition.source.level_uid in scope.level_uids
            and transition.destination.level_uid in scope.level_uids
        )
        if transition.origin == TransitionOrigin.RUNTIME or entry.directional or not interior:
            sql.append(transition)
        else:
            packed.setdefault(scope.building_uid, []).append(transition)
    return TransitionPartition(tuple(sql), {uid: tuple(items) for uid, items in packed.items()})
