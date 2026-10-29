"""BasinSpec — bathymetry intent for one resolved water body (HY-12 step 3a)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import TypeAdapter

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.identity.uid import EntityUid
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.terrain.relief.bathymetry.floorProfile import BasinFloorProfile, FieldFloorProfile, SampledFloorProfile
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace


@dataclass(frozen=True)
class BasinSpec:
    source_uid: EntityUid
    kind: BasinKind
    liquid: MaterialKey
    footprint: frozenset[Coord]
    z_water_level: int
    floor_z: int
    bands: HydrologyBands
    floor_profile: BasinFloorProfile | None = None

    def __post_init__(self) -> None:
        if not self.footprint:
            raise ValueError(f"basin {self.source_uid}: footprint must be nonempty")
        if self.floor_z >= self.z_water_level:
            raise ValueError(f"basin {self.source_uid}: floor_z must be below z_water_level")
        if self.floor_profile is None:
            return
        if not isinstance(self.floor_profile, (FieldFloorProfile, SampledFloorProfile)):
            raise TypeError("basin floor requires a typed profile")
        profile = TypeAdapter(BasinFloorProfile).validate_python(self.floor_profile, strict=True)
        object.__setattr__(self, "floor_profile", profile)
        if isinstance(profile, FieldFloorProfile):
            if profile.level != self.z_water_level or self.floor_z != max(profile.z_min, profile.level - profile.depth):
                raise ValueError("basin field profile must match its level and floor bound")
        else:
            if profile.space is CoordinateSpace.LOCATION_FINE_GRID:
                raise ValueError("basin sampled profile requires world coordinates")
            if frozenset(cell for cell, _ in profile.samples) != self.footprint:
                raise ValueError("basin sampled profile must cover the exact accepted footprint")
            if self.floor_z != min(z for _, z in profile.samples) or any(z >= self.z_water_level for _, z in profile.samples):
                raise ValueError("basin sampled profile must match its minimum and stay below level")
