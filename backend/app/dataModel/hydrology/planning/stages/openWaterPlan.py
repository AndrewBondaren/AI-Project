"""Accepted open-water facts passed between hydrology stage owners."""

from typing import Self
from dataclasses import dataclass

from app.dataModel.topology.worldTopology import Coord
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
from app.dataModel.hydrology.planning.hydrologyPlan import coarse_order, require_map, require_unique_water
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord


class OpenWaterPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    coarse_open_water: tuple[tuple[SurfaceGridCoord, MapCellHydrology], ...]
    water_bodies: tuple[WaterBody, ...]
    physical_unions: tuple[PhysicalWaterUnion, ...]
    source_mapping: SourceBodyMapping

    @model_validator(mode="after")
    def consistent_water(self) -> Self:
        require_map(self.coarse_open_water, coarse_order)
        require_unique_water(self.water_bodies, self.physical_unions)
        bodies = {body.water_body_uid for body in self.water_bodies}
        if any(uid not in bodies for entry in self.source_mapping.entries for uid in entry.body_uids):
            raise ValueError("open water source mapping requires final physical body UIDs")
        return self


@dataclass(frozen=True)
class MaterializedWater:
    cells: tuple[tuple[Coord, MapCellHydrology], ...]
    bodies: tuple[WaterBody, ...]
    area_rows: tuple[tuple[str, int], ...]
    floor_rows: tuple[tuple[str, int], ...]
    uid_aliases: tuple[tuple[str, str], ...]
    source_mapping: SourceBodyMapping

    def __post_init__(self) -> None:
        bodies = require_unique_water(self.bodies, ())
        coords = tuple((cell[1], cell[0]) for cell, _ in self.cells)
        if coords != tuple(sorted(set(coords))):
            raise ValueError("materialized cells require unique canonical row order")
        for rows in (self.area_rows, self.floor_rows, self.uid_aliases):
            keys = tuple(key for key, _ in rows)
            if keys != tuple(sorted(set(keys))):
                raise ValueError("materialized indexes require unique canonical UID order")
        if any((value.water_body_uid is not None and value.water_body_uid not in bodies)
               or value.liquid_candidate and value.water_body_uid is None for _, value in self.cells):
            raise ValueError("materialized cell requires its final physical body identity")
        if any(uid not in bodies for entry in self.source_mapping.entries for uid in entry.body_uids):
            raise ValueError("materialized source mapping requires final physical body identities")

@dataclass(frozen=True)
class AssembledWater:
    materialized: MaterializedWater
    physical_unions: tuple[PhysicalWaterUnion, ...]

    def __post_init__(self) -> None:
        require_unique_water(self.materialized.bodies, self.physical_unions)
        bodies = {body.water_body_uid for body in self.materialized.bodies}
        if any(uid not in bodies for union in self.physical_unions for uid in union.member_uids):
            raise ValueError("physical union requires final materialized members")


type FineWaterResult = tuple[FineSurfaceWindow, AssembledWater]
