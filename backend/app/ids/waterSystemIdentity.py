"""Shared water-system DET-1 identity, used by physical producers and W/L."""

from collections.abc import Iterable

from app.dataModel.hydrology.enums.waterSystemKind import WaterSystemKind
from app.ids.deterministicIds import entity_uid, state_fingerprint
from app.ids.uidKind import UidKind


def water_system_uid(world_uid: str, change_uid: str, members: Iterable[str],
                     kind: WaterSystemKind) -> str:
    members = tuple(sorted(set(members)))
    if not world_uid or not change_uid or not members or any(not uid for uid in members):
        raise ValueError("water system requires world, operation and nonempty member UIDs")
    return entity_uid(world_uid, UidKind.WATER_SYSTEM, change_uid=change_uid,
                      members=state_fingerprint(members), system_kind=kind)


def initial_water_change_uid(world_uid: str) -> str:
    """Logical bootstrap operation; stateful updates must supply their own change UID.

    Pure first-bake/preview retries replay this operation. This is never used as
    an operation identifier for drought/refill or other persisted W/L updates.
    """
    return entity_uid(world_uid, UidKind.LIFECYCLE_CHANGE, scope="hydrology", origin="bootstrap")
