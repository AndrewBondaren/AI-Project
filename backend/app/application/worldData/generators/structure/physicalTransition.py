"""Physical aggregate construction and final geometry identity for structure producers."""

from collections.abc import Callable

from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint, TransitionSpace
from app.dataModel.locations.transitions.transitionSide import TransitionSide
from app.db.models.locationLevel import LocationLevel


def level_endpoint(level: LocationLevel, x: int, y: int, building_uid: str) -> TransitionEndpoint:
    return TransitionEndpoint(space=TransitionSpace.LEVEL, level_uid=level.level_uid,
                              host_location_uid=building_uid, x=x, y=y, z=level.z)


def physical_transition(world_uid: str, system_type: str, source: TransitionEndpoint,
                        destination: TransitionEndpoint, building_uid: str, **fields) -> Transition:
    return Transition(
        transition_uid=transition_uid(world_uid, system_type, source, destination),
        world_uid=world_uid, system_transition_type=system_type,
        source=source, destination=destination,
        source_side=TransitionSide(owner_location_uid=building_uid if source.space == TransitionSpace.LEVEL else None),
        destination_side=TransitionSide(owner_location_uid=building_uid), **fields,
    )


def transform_transition(item: Transition, point: Callable[[int, int], tuple[int, int]], dz: int = 0) -> Transition:
    def endpoint(old: TransitionEndpoint) -> TransitionEndpoint:
        if old.geometry is None:
            return old
        x, y = point(old.x, old.y)
        return old.model_copy(update={"x": x, "y": y, "z": old.z + dz})
    source, destination = endpoint(item.source), endpoint(item.destination)
    return item.model_copy(update={
        "source": source, "destination": destination,
        "transition_uid": transition_uid(item.world_uid, item.system_transition_type, source, destination),
    })
