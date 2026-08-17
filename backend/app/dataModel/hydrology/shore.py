"""default_shore — REF-W terrain/material for shore cells.

World-level ``hydrology.default_shore`` is deprecated. Paint from
``default_rivers.shore`` / ``mountain_shore``, ``default_lakes.shore``,
``default_seas.shore`` (tz_terrain_hydrology U15).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import StrictOnWire
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


class HydrologyShoreDefaults(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_terrain: StrictOnWire[str] = "shore"
    system_material: StrictOnWire[str] = "sand"

    @classmethod
    def for_condition(cls, terrain: ReliefConditionTerrain) -> HydrologyShoreDefaults:
        """Category paint default: R34 key + registry ``default_material``."""
        entry = WorldTerrainRegistry.canonical_defaults().entry_for(terrain.value)
        if entry is None or not entry.default_material:
            raise RuntimeError(
                f"WorldTerrainRegistry missing default_material for {terrain.value!r}"
            )
        return cls(
            system_terrain=terrain.value,
            system_material=str(entry.default_material),
        )
