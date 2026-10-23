"""BasinSpec — bathymetry intent for one resolved water body (HY-12 step 3a)."""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.identity.uid import EntityUid
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.topology.worldTopology import Coord


@dataclass(frozen=True)
class BasinSpec:
    source_uid: EntityUid
    kind: BasinKind
    liquid: MaterialKey
    footprint: frozenset[Coord]
    z_water_level: int
    floor_z: int
    bands: HydrologyBands

    def __post_init__(self) -> None:
        if not self.footprint:
            raise ValueError(f"basin {self.source_uid}: footprint must be nonempty")
        if self.floor_z >= self.z_water_level:
            raise ValueError(f"basin {self.source_uid}: floor_z must be below z_water_level")
