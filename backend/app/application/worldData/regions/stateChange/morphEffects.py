"""Signals for domain materializers; evaluating state never paints or carves."""

from dataclasses import dataclass

from app.dataModel.regions.regionState import RegionState
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrainMasks.regions import RegionSpecBase


@dataclass(frozen=True, kw_only=True)
class MaterializeSignal:
    region_uid: str
    parent_region_uid: str | None
    spec: RegionSpecBase
    previous: RegionState | None
    state: RegionState
    # The domain consumes registry metadata at refine, including N+1 keys.
    target: TerrainRegistryEntry


def signal_for(*, spec: RegionSpecBase, previous: RegionState | None,
               state: RegionState, target: TerrainRegistryEntry,
               parent_region_uid: str | None = None) -> MaterializeSignal | None:
    if previous == state:
        return None
    if previous is not None and (previous.current_type, previous.overrides, previous.tombstone,
                                 previous.spec_fingerprint) == (
            state.current_type, state.overrides, state.tombstone, state.spec_fingerprint):
        return None
    return MaterializeSignal(region_uid=state.region_uid, parent_region_uid=parent_region_uid,
                             spec=spec, previous=previous, state=state, target=target)
