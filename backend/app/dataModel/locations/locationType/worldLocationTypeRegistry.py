"""Root POJO for `worlds.location_type_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.locations.locationType.locationTypeEntry import LocationTypeEntry
from app.dataModel.locations.locationType.locationTypeSubtypeEntry import LocationTypeSubtypeEntry

_CANONICAL_ENTRIES: tuple[LocationTypeEntry, ...] = (
    LocationTypeEntry(system_type="region", display_type="Регион"),
    LocationTypeEntry(system_type="territory", display_type="Территория"),
    LocationTypeEntry(system_type="settlement", display_type="Поселение"),
    LocationTypeEntry(system_type="district", display_type="Район"),
    LocationTypeEntry(system_type="building", display_type="Строение"),
    LocationTypeEntry(system_type="room", display_type="Помещение"),
    LocationTypeEntry(system_type="geographic", display_type="География"),
    LocationTypeEntry(system_type="climate_pole", display_type="Климатический полюс"),
)

_ENGINE_ENTRIES: tuple[LocationTypeEntry, ...] = (
    LocationTypeEntry(
        system_type="region",
        display_type="Регион",
        parent_types=[None],
        is_outdoor=True,
    ),
    LocationTypeEntry(
        system_type="territory",
        display_type="Территория",
        parent_types=["region"],
        is_outdoor=True,
        subtypes=[
            LocationTypeSubtypeEntry(system_subtype="island", border_category="liquid"),
            LocationTypeSubtypeEntry(system_subtype="mountain"),
            LocationTypeSubtypeEntry(system_subtype="underground"),
        ],
    ),
    LocationTypeEntry(
        system_type="settlement",
        display_type="Поселение",
        parent_types=["territory"],
        is_outdoor=True,
        subtypes=[
            LocationTypeSubtypeEntry(system_subtype="city"),
            LocationTypeSubtypeEntry(system_subtype="village"),
            LocationTypeSubtypeEntry(system_subtype="dungeon"),
            LocationTypeSubtypeEntry(system_subtype="underground_city"),
        ],
    ),
    LocationTypeEntry(
        system_type="district",
        display_type="Район",
        parent_types=["settlement"],
        is_outdoor=True,
    ),
    LocationTypeEntry(
        system_type="building",
        display_type="Строение",
        parent_types=["settlement", "district"],
        is_outdoor=False,
        subtypes=[
            LocationTypeSubtypeEntry(system_subtype="residential"),
            LocationTypeSubtypeEntry(system_subtype="commercial"),
            LocationTypeSubtypeEntry(system_subtype="military"),
            LocationTypeSubtypeEntry(system_subtype="religious"),
        ],
    ),
    LocationTypeEntry(
        system_type="room",
        display_type="Помещение",
        parent_types=["building"],
        is_outdoor=False,
        subtypes=[
            LocationTypeSubtypeEntry(system_subtype="porch"),
            LocationTypeSubtypeEntry(system_subtype="entrance_steps"),
        ],
    ),
    LocationTypeEntry(
        system_type="geographic",
        display_type="География",
        parent_types=["region", "territory", None],
        is_outdoor=True,
        subtypes=[
            LocationTypeSubtypeEntry(system_subtype="mountain"),
            LocationTypeSubtypeEntry(system_subtype="peak"),
            LocationTypeSubtypeEntry(system_subtype="plain"),
            LocationTypeSubtypeEntry(system_subtype="hill"),
            LocationTypeSubtypeEntry(system_subtype="lake", border_category="liquid"),
            LocationTypeSubtypeEntry(system_subtype="sea", border_category="liquid"),
            LocationTypeSubtypeEntry(system_subtype="ocean", border_category="liquid"),
            LocationTypeSubtypeEntry(system_subtype="inland_sea", border_category="liquid"),
            LocationTypeSubtypeEntry(system_subtype="island", border_category="liquid"),
            LocationTypeSubtypeEntry(system_subtype="coast"),
            LocationTypeSubtypeEntry(system_subtype="river"),
        ],
    ),
    LocationTypeEntry(
        system_type="climate_pole",
        display_type="Климатический полюс",
        parent_types=[None],
        is_outdoor=True,
    ),
)


class WorldLocationTypeRegistry(RootModel[list[LocationTypeEntry]]):
    """Root POJO for `worlds.location_type_registry`. Wire shape: JSON array (map normalized on import)."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-LOC-TYPE"

    root: list[LocationTypeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldLocationTypeRegistry:
        """fixtures/world_template.json — minimal map rows after JV normalize."""
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def canonical_engine(cls) -> WorldLocationTypeRegistry:
        """tz_locations.md § location_type_registry — full hierarchy + subtypes."""
        return cls(list(_ENGINE_ENTRIES))

    def entry_for(self, system_type: str) -> LocationTypeEntry | None:
        for entry in self.root:
            if entry.system_type == system_type:
                return entry
        return None

    def subtype_for(self, system_type: str, system_subtype: str) -> LocationTypeSubtypeEntry | None:
        entry = self.entry_for(system_type)
        if entry is None:
            return None
        for subtype in entry.subtypes:
            if subtype.system_subtype == system_subtype:
                return subtype
        return None

    def allows_parent(self, child_system_type: str, parent_system_type: str | None) -> bool:
        entry = self.entry_for(child_system_type)
        if entry is None:
            return False
        return parent_system_type in entry.parent_types
