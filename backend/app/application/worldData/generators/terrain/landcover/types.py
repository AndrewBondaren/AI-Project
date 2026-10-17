"""Resolved plugin inputs, separate from authored declarations and future SQL rows."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.application.worldData.masks.regionRasterContext import RegionClaim
from app.application.worldData.regions.regionFacts import RegionFacts
from app.dataModel.spatial.facing import Facing
from app.dataModel.spatial.regionShape import Point
from app.dataModel.terrainMasks.regions import LandcoverDeclareEntry, RegionSpecBase
from app.dataModel.worldPack.wire.worldTopology import WorldTopology


class RegionSource(StrEnum):
    DECLARED = "declared"
    ANCHOR = "anchor"
    AUTORESOLVE = "autoresolve"


@dataclass(frozen=True)
class StateSnapshotEntry:
    current_type: str
    tombstone: bool = False


@dataclass(frozen=True)
class AnchoredRegion:
    anchor_uid: str
    spec: LandcoverDeclareEntry


@dataclass(frozen=True)
class Sublocation:
    seed_xy: Point
    region_uid: str
    facing: Facing | None
    placement_specificity: int | None = None


@dataclass(frozen=True)
class ResolvedRegion:
    world_uid: str
    region_uid: str
    spec: RegionSpecBase
    current_type: str
    source: RegionSource
    topology: WorldTopology
    claim: RegionClaim | None = None
    sublocations: tuple[Sublocation, ...] = ()
    claim_area: float | None = None


@dataclass(frozen=True)
class LandcoverInputs:
    topology: WorldTopology
    # Coordinates are world fine cells. The caller prepares the fact consumers/context.
    facts_at: Callable[[Point], RegionFacts]
    # Explicit complete read snapshot. No absent-reader => empty-store fallback.
    state_snapshot: Mapping[str, StateSnapshotEntry]
    anchor_specs: tuple[AnchoredRegion, ...] = ()
