"""Root POJO for `worlds.district_template_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.registryKey import RegistryKey
from app.dataModel.roads.enums.streetLayout import StreetLayout
from app.dataModel.settlement.district.districtConnection import DistrictConnection
import app.dataModel.settlement.district.districtTemplateEntry as _entry_mod
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.placementCondition import PlacementCondition
from app.dataModel.settlement.district.requiredStructure import POSITION_CENTER, RequiredStructure
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
    WorldSettlementSizeRegistry,
)

_RANK_MEDIUM = WorldSettlementSizeRegistry.default_system_size()


class WorldDistrictTemplateRegistry(RootModel[list[DistrictTemplateEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-DISTRICT-TEMPLATE"
    # Runtime worldRow: canonical ⊕ world overrides by this entry field (T-29).
    RUNTIME_MERGE_ID_FIELD: ClassVar[str] = "system_name"
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


type DistrictTemplateKey = RegistryKey[WorldDistrictTemplateRegistry]

_entry_mod.WorldDistrictTemplateRegistry = WorldDistrictTemplateRegistry
DistrictTemplateEntry.model_rebuild()

_CANONICAL_ENTRIES: tuple[DistrictTemplateEntry, ...] = (
    DistrictTemplateEntry(
        system_name="civic_center",
        display_name="Центральный квартал",
        district_type="civic",
        placement_conditions=[
            PlacementCondition(type="min_settlement_size", size=_RANK_MEDIUM),
            PlacementCondition(type="cell_zone", zone="center"),
        ],
        max_per_city=1,
        allowed_structure_types=["town_hall"],
        required_structures=[
            RequiredStructure(building_template="town_hall", count=1, position=POSITION_CENTER),
        ],
        street_layout=StreetLayout.GRID,
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
    DistrictTemplateEntry(
        system_name="commercial_quarter",
        display_name="Торговый квартал",
        district_type="commercial",
        street_layout=StreetLayout.GRID,
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
    DistrictTemplateEntry(
        system_name="residential_quarter",
        display_name="Жилой квартал",
        district_type="residential",
        street_layout=StreetLayout.GRID,
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
    DistrictTemplateEntry(
        system_name="industrial_quarter",
        display_name="Промышленный квартал",
        district_type="industrial",
        placement_conditions=[PlacementCondition(type="min_settlement_size", size=_RANK_MEDIUM)],
        street_layout=StreetLayout.GRID,
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
                min_adjacent_cells=1,
            ),
            PlacementCondition(type="min_settlement_size", size=_RANK_MEDIUM),
        ],
        max_per_city=1,
        street_layout=StreetLayout.GRID,
        density="dense",
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
    DistrictTemplateEntry(
        system_name="mining_quarter",
        display_name="Добывающий квартал",
        district_type="industrial",
        district_subtype="extract",
        street_layout=StreetLayout.GRID,
        allowed_structure_types=["mine"],
        connections=[
            DistrictConnection(connection_type="road", role="service_road", sidewalk=False),
        ],
    ),
    DistrictTemplateEntry(
        system_name="processing_quarter",
        display_name="Квартал обработки",
        district_type="industrial",
        district_subtype="process",
        street_layout=StreetLayout.GRID,
        allowed_structure_types=["mill", "smelter"],
        connections=[
            DistrictConnection(connection_type="road", role="service_road", sidewalk=False),
        ],
    ),
    DistrictTemplateEntry(
        system_name="manufacture_quarter",
        display_name="Квартал производства",
        district_type="industrial",
        district_subtype="manufacture",
        street_layout=StreetLayout.GRID,
        allowed_structure_types=["workshop"],
        connections=[
            DistrictConnection(connection_type="road", role="service_road", sidewalk=False),
        ],
    ),
    DistrictTemplateEntry(
        system_name="cultural_quarter",
        display_name="Культурный квартал",
        district_type="civic",
        district_subtype="culture",
        street_layout=StreetLayout.GRID,
        allowed_structure_types=["temple", "theater", "library"],
        connections=[
            DistrictConnection(connection_type="road", role="main_street", sidewalk=True),
        ],
    ),
    DistrictTemplateEntry(
        system_name="farm_quarter",
        display_name="Аграрный квартал",
        district_type="agricultural",
        district_subtype="farm",
        street_layout=StreetLayout.GRID,
        allowed_structure_types=["farm", "mill"],
        connections=[
            DistrictConnection(connection_type="road", role="service_road", sidewalk=False),
        ],
    ),
    DistrictTemplateEntry(
        system_name="livestock_quarter",
        display_name="Скотоводческий квартал",
        district_type="agricultural",
        district_subtype="livestock",
        street_layout=StreetLayout.GRID,
        allowed_structure_types=["livestock"],
        connections=[
            DistrictConnection(connection_type="road", role="service_road", sidewalk=False),
        ],
    ),
)
