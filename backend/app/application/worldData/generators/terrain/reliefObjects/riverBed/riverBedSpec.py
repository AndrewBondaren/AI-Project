"""Absolute post-planning river profile; vertices retain every vertical step."""

from dataclasses import dataclass

from app.dataModel.topology.worldTopology import Coord


@dataclass(frozen=True)
class RiverBedSpec:
    bed_z: tuple[tuple[Coord, int], ...]
