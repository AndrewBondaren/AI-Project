"""Async entity-store read before synchronous bake/refine computation."""

from collections.abc import Mapping
from types import MappingProxyType

from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
from app.application.worldData.regions.regionStateMapping import state_from_row
from app.db.repositories.iRegionStateRepository import IRegionStateRepository


async def load_region_state_snapshot(repo: IRegionStateRepository | None,
                                     world_uid: str) -> Mapping[str, StateSnapshotEntry]:
    if repo is None:
        return MappingProxyType({})
    result = {}
    for row in await repo.get_by_world(world_uid):
        if row.world_uid != world_uid:
            raise ValueError("region state snapshot contains another world")
        state = state_from_row(row)
        result[state.region_uid] = StateSnapshotEntry(
            state.current_type, state.tombstone, state.spec_fingerprint)
    return MappingProxyType(result)
