"""Pre-relief observations owned by terrain, independent of final hydrology."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Self

from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.topology.worldTopology import Coord


@dataclass(frozen=True, slots=True)
class TerrainWorkingFields:
    relief_z: Mapping[Coord, int]

    @classmethod
    def from_plan(cls, plan: TerrainPlan) -> Self:
        return cls(MappingProxyType({(cell.gx, cell.gy): z for cell, z in plan.surface_z}))
