"""Root POJO for `worlds.district_template_registry`."""

from __future__ import annotations

from pydantic import RootModel

from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.placementCondition import PlacementCondition


class WorldDistrictTemplateRegistry(RootModel[list[DistrictTemplateEntry]]):
    root: list[DistrictTemplateEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldDistrictTemplateRegistry:
        return cls([])

    @classmethod
    def example_port_district(cls) -> DistrictTemplateEntry:
        """Reference row from tz_city_generation.md §9.3."""
        return DistrictTemplateEntry(
            system_name="port_district",
            display_name="Портовый район",
            district_type="port",
            max_per_city=1,
            placement_conditions=[
                PlacementCondition(
                    type="adjacent_terrain",
                    terrain_types=["liquid_body"],
                    min_count=1,
                ),
                PlacementCondition(type="min_city_size", size="town"),
            ],
            allowed_structure_types=["warehouse", "tavern", "shop", "guild"],
            density="dense",
        )
