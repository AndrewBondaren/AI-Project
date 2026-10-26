"""Pure reference validation against caller snapshots; no hierarchy or traversal policy."""

from collections.abc import Mapping, Sequence

from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint, TransitionSpace
from app.dataModel.locations.transitions.transitionSide import TransitionSideId
from app.dataModel.locations.transitions.transitionType import TransitionVertical
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationLevel import LocationLevel
from app.db.models.namedLocation import NamedLocation


class TransitionValidationError(ValueError):
    pass


def _location(uid: str, world_uid: str, locations: Mapping[str, NamedLocation]) -> NamedLocation:
    location = locations.get(uid)
    if location is None or location.location_uid != uid:
        raise TransitionValidationError(f"unknown location {uid!r}")
    if location.world_uid != world_uid:
        raise TransitionValidationError(f"location {uid!r} belongs to another world")
    return location


def _endpoint(
    endpoint: TransitionEndpoint,
    *,
    world_uid: str,
    levels: Mapping[str, LocationLevel],
    locations: Mapping[str, NamedLocation],
    nodes: Mapping[str, ConnectionNode],
) -> None:
    if endpoint.host_location_uid is not None:
        _location(endpoint.host_location_uid, world_uid, locations)
    if endpoint.space == TransitionSpace.LEVEL:
        level = levels.get(endpoint.level_uid)
        if level is None or level.level_uid != endpoint.level_uid:
            raise TransitionValidationError(f"unknown level {endpoint.level_uid!r}")
        _location(level.location_uid, world_uid, locations)
        if endpoint.host_location_uid is not None and endpoint.host_location_uid != level.location_uid:
            raise TransitionValidationError("level endpoint host differs from level location")
        if not level.z <= endpoint.z < level.z + level.z_height:
            raise TransitionValidationError("endpoint z is outside its level")
    if endpoint.node_uid is not None:
        node = nodes.get(endpoint.node_uid)
        if node is None or node.node_uid != endpoint.node_uid:
            raise TransitionValidationError(f"unknown node {endpoint.node_uid!r}")
        if node.world_uid != world_uid:
            raise TransitionValidationError("endpoint node belongs to another world")
        if endpoint.geometry is None or endpoint.geometry != (node.x, node.y, node.z):
            raise TransitionValidationError("node requires matching concrete endpoint geometry")


def validate_transitions(
    world_uid: str,
    transitions: Sequence[Transition],
    *,
    levels: Mapping[str, LocationLevel],
    locations: Mapping[str, NamedLocation],
    nodes: Mapping[str, ConnectionNode],
    registry: WorldTransitionTypeRegistry,
) -> None:
    """Validate the complete aggregate, including model_copy updates, before writing.

    Owners are optional and independent of hosts. A level's world is checked
    through its explicit location. Parent links and side access state are ignored.
    """
    for transition in transitions:
        try:
            validated = Transition.model_validate(
                transition.model_dump(mode="json"),
                context={"transition_type_registry": registry},
            )
            if validated.world_uid != world_uid:
                raise TransitionValidationError("transition belongs to another world")
            for side_id in TransitionSideId:
                endpoint = getattr(validated, side_id.value)
                state = getattr(validated, f"{side_id}_side")
                _endpoint(endpoint, world_uid=world_uid, levels=levels, locations=locations, nodes=nodes)
                if state.owner_location_uid is not None:
                    _location(state.owner_location_uid, world_uid, locations)
            source, destination = validated.source.geometry, validated.destination.geometry
            if source is not None and destination is not None:
                vertical = registry.entry_for(validated.system_transition_type).vertical
                if vertical == TransitionVertical.NONE and source[2] != destination[2]:
                    raise TransitionValidationError("horizontal type requires equal endpoint z")
                if vertical == TransitionVertical.REQUIRED and source[2] == destination[2]:
                    raise TransitionValidationError("vertical type requires different endpoint z")
                if vertical == TransitionVertical.DOWN and source[2] <= destination[2]:
                    raise TransitionValidationError("fall destination must be below source")
        except ValueError as exc:
            raise TransitionValidationError(f"transition {transition.transition_uid!r}: {exc}") from exc
