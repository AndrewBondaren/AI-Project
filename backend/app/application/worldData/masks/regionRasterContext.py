"""Resolved inputs for pure region rasterization; no world-policy defaults here."""

from dataclasses import dataclass
from typing import Protocol

from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.spatial.regionShape import EdgeNoise, Point
from app.dataModel.terrainMasks.regions import RegionSpecBase
from app.dataModel.worldPack.wire.worldBounds import WorldBounds
from app.dataModel.worldPack.wire.worldTopology import WorldTopology


class RasterWorld(Protocol):
    world_uid: str


def fine_topology(topology: WorldTopology, tile_macro: int) -> WorldTopology:
    """Macro-tile topology lifted to fine cells; the same seam rules apply."""
    bounds = topology.bounds
    return WorldTopology(mode=topology.mode, bounds=WorldBounds(
        x_min=bounds.x_min * tile_macro, x_max=(bounds.x_max + 1) * tile_macro - 1,
        y_min=bounds.y_min * tile_macro, y_max=(bounds.y_max + 1) * tile_macro - 1,
    ))


@dataclass(frozen=True)
class RegionRasterContext:
    region_uid: str
    spec: RegionSpecBase
    scale: LightGridScale
    topology: WorldTopology
    """Resolved topology in macro-tile coordinates, including sphere parity."""

    def fine_topology(self) -> WorldTopology:
        return fine_topology(self.topology, self.scale.tile_m)


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
