"""Caller-owned observation scopes; runtime geometry is a materialization signal."""

from dataclasses import dataclass

from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import DeclarationFacts
from app.dataModel.regions.regionState import RegionState, RegionStateOverrides, RegionTransitionCause
from app.dataModel.spatial.regionShape import Point
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.terrainMasks.regions import RegionSpecBase


@dataclass(frozen=True, kw_only=True)
class SpatialEvaluation:
    # Stable lowland-cluster identity, independent of target and evaluation time.
    seed_xy: Point
    spec: RegionSpecBase
    context: FactConsumerContext


@dataclass(frozen=True, kw_only=True)
class RegionEvaluation:
    region_uid: str
    entry_type: TerrainKey
    spec: RegionSpecBase
    spec_fingerprint: str
    context: FactConsumerContext
    elapsed_ticks: int
    at: str | int
    # SQL audit marker comes from the external caller, never a simulated clock.
    updated_at: str
    declaration: DeclarationFacts | None = None
    cause: RegionTransitionCause = RegionTransitionCause.DRIFT
    overrides: RegionStateOverrides | None = None
    # Required for distinguishing authored type edits from shape-only edits.
    previous_entry_type: TerrainKey | None = None
    spatial: tuple[SpatialEvaluation, ...] = ()


@dataclass(frozen=True, kw_only=True)
class ChildRegion:
    region_uid: str
    parent_region_uid: str
    seed_xy: Point
    entry_type: TerrainKey
    spec: RegionSpecBase
    state: RegionState
