"""Resolved inputs for pure region rasterization; no world-policy defaults here."""

from dataclasses import dataclass
from typing import Protocol

from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.spatial.regionShape import EdgeNoise, Point
from app.dataModel.terrainMasks.regions import RegionSpecBase
from app.dataModel.topology.fineTopology import fine_topology as fine_topology
from app.dataModel.topology.worldTopology import WorldTopology


class RasterWorld(Protocol):
    @property
    def world_uid(self) -> str: ...


@dataclass(frozen=True)
class RegionRasterContext:
    region_uid: str
    spec: RegionSpecBase
    scale: LightGridScale
    topology: WorldTopology
    """Resolved topology in macro-tile coordinates, including sphere parity."""

    def fine_topology(self) -> WorldTopology:
        return fine_topology(self.topology, self.scale.tile_macro)


@dataclass(frozen=True, order=True)
class ClaimSeed:
    coord: Point
    region_uid: str


@dataclass(frozen=True)
class RegionClaim:
    """Given seeds, a graph-distance cap in fine cells, and boundary noise.

    No seed generation, region merging or implicit claim-policy values.
    """

    seeds: tuple[ClaimSeed, ...]
    max_radius: int
    noise: EdgeNoise

    def __post_init__(self) -> None:
        if self.max_radius < 0:
            raise ValueError("claim max_radius must be nonnegative")
