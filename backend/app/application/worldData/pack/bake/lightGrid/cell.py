"""Mutable staging mirror of WorldMapCellWire — not SoT (tz_map_light_bake)."""

from __future__ import annotations

from dataclasses import dataclass

from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


@dataclass
class LightGridCell:
    surface_z: int = 0
    system_terrain: str | None = None
    dominant_terrain_id: int = 0
    hydrology_role: WorldMapHydrologyRole = WorldMapHydrologyRole.NONE
    hydrology_width: int | None = None
    climate_zone_id: int | None = None
    location_pin: int | None = None

    def to_wire(self, tx: int, ty: int) -> WorldMapCellWire:
        return WorldMapCellWire(
            tx=tx,
            ty=ty,
            surface_z=self.surface_z,
            system_terrain=self.system_terrain,
            dominant_terrain_id=self.dominant_terrain_id,
            hydrology_role=self.hydrology_role,
            hydrology_width=self.hydrology_width,
            climate_zone_id=self.climate_zone_id,
            location_pin=self.location_pin,
        )

    @classmethod
    def from_wire_defaults(cls) -> LightGridCell:
        d = WorldMapCellWire(tx=0, ty=0)
        return cls(
            surface_z=d.surface_z,
            system_terrain=d.system_terrain,
            dominant_terrain_id=d.dominant_terrain_id,
            hydrology_role=d.hydrology_role,
            hydrology_width=d.hydrology_width,
            climate_zone_id=d.climate_zone_id,
            location_pin=d.location_pin,
        )
