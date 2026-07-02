"""Root POJO for `worlds.district_template_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.settlement.district.districtConnection import DistrictConnection
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.placementCondition import PlacementCondition
from app.dataModel.settlement.district.requiredStructure import RequiredStructure

_CANONICAL_ENTRIES: tuple[DistrictTemplateEntry, ...] = (
    DistrictTemplateEntry(
        system_name="civic_center",
        display_name="Центральный квартал",
        district_type="civic",
        placement_conditions=[
            PlacementCondition(type="min_city_size", size="town"),
            PlacementCondition(type="cell_zone", zone="center"),
        ],
        max_per_city=1,
        required_structures=[
            RequiredStructure(building_template="town_hall", count=1, position="center"),
        ],
        street_layout="grid",
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
    DistrictTemplateEntry(
        system_name="commercial_quarter",
        display_name="Торговый квартал",
        district_type="commercial",
        street_layout="grid",
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
    DistrictTemplateEntry(
        system_name="residential_quarter",
        display_name="Жилой квартал",
        district_type="residential",
        street_layout="grid",
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
    DistrictTemplateEntry(
        system_name="industrial_quarter",
        display_name="Промышленный квартал",
        district_type="industrial",
        placement_conditions=[PlacementCondition(type="min_city_size", size="town")],
        street_layout="grid",
        connections=[
            DistrictConnection(connection_type="road", role="service_road", sidewalk=False),
        ],
    ),
    DistrictTemplateEntry(
        system_name="port_district",
        display_name="Портовый район",
        district_type="port",
        placement_conditions=[
            PlacementCondition(
                type="adjacent_terrain",
                terrain_types=["liquid_body"],
                min_count=1,
            ),
            PlacementCondition(type="min_city_size", size="town"),
        ],
        max_per_city=1,
        street_layout="grid",
        density="dense",
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
)


class WorldDistrictTemplateRegistry(RootModel[list[DistrictTemplateEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-DISTRICT-TEMPLATE"
    root: list[DistrictTemplateEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldDistrictTemplateRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def example_port_district(cls) -> DistrictTemplateEntry:
        """Alias — port row from builtin catalog."""
        entry = cls.canonical_defaults().entry_for("port_district")
        assert entry is not None
        return entry

    def entry_for(self, system_name: str) -> DistrictTemplateEntry | None:
        for entry in self.root:
            if entry.system_name == system_name:
                return entry
        return None
