"""Root POJO for `worlds.climate_zone_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.climate.climateZone.climateZoneEntry import ClimateZoneEntry
from app.dataModel.climate.enums.climateZone import ClimateZone


class WorldClimateZoneRegistry(RootModel[list[ClimateZoneEntry]]):
    """Root POJO for `worlds.climate_zone_registry`. Wire shape: JSON array."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-CLIMATE-ZONE"

    root: list[ClimateZoneEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldClimateZoneRegistry:
        """fixtures/world_template.json — wire-template subset."""
        return cls([z.to_entry(wire=True) for z in ClimateZone.wire_template_members()])

    @classmethod
    def canonical_engine(cls) -> WorldClimateZoneRegistry:
        """Built-in engine enum profiles."""
        return cls([z.to_entry() for z in ClimateZone.engine_members()])

    def entry_for(self, system_climate: str) -> ClimateZoneEntry | None:
        for entry in self.root:
            if entry.system_climate == system_climate:
                return entry
        return None
