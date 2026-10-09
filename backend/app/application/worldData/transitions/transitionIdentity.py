"""Physical transition identity — transitions §2 invariant 10, storage DET-1."""

from app.ids import UidKind, entity_uid
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transitionSide import TransitionSideId
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import TransitionTypeKey


def transition_uid(
    world_uid: str,
    system_type: TransitionTypeKey,
    source: TransitionEndpoint,
    destination: TransitionEndpoint,
) -> str:
    """Mint once from final global endpoints, after placement/rotation/z adjustment.

    Keys: type and source_/destination_ prefixed Endpoint.identity_keys(). The shared helper
    sorts key names; endpoints retain their semantic source/destination order. SQL and pack
    carry this UID without minting again. Runtime creation uses ids.runtime_uid.
    Mutable portal destination identity is outside this physical contract.
    """
    keys = {
        f"{side}_{key}": value
        for side, endpoint in ((TransitionSideId.SOURCE, source),
                              (TransitionSideId.DESTINATION, destination))
        for key, value in endpoint.identity_keys().items()
    }
    return entity_uid(world_uid, UidKind.TRANSITION, type=system_type, **keys)
