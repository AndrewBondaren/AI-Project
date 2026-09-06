"""Root POJO for `worlds.location_type_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.locations.locationType.locationTypeEntry import LocationTypeEntry
from app.dataModel.locations.locationType.locationTypeSubtypeEntry import LocationTypeSubtypeEntry

# tz_locations.md § location_type_registry — full hierarchy + subtypes (engine SoT).
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
            LocationTypeSubtypeEntry(
                system_subtype="city",
                l0_map_symbol="u",
                typical_district_types=[
                    "civic", "commercial", "residential", "industrial", "port",
                ],
                required_structure_types=["town_hall"],
            ),
            LocationTypeSubtypeEntry(
                system_subtype="village",
                l0_map_symbol="n",
                typical_district_types=["civic", "residential"],
            ),
            LocationTypeSubtypeEntry(system_subtype="dungeon", l0_map_symbol="d"),
            LocationTypeSubtypeEntry(
                system_subtype="underground_city",
                l0_map_symbol="g",
                typical_district_types=["civic", "residential"],
            ),
        ],
    ),
    LocationTypeEntry(
        system_type="district",
        display_type="Район",
        parent_types=["settlement"],
        is_outdoor=True,
        subtypes=[
            LocationTypeSubtypeEntry(system_subtype="extract"),
            LocationTypeSubtypeEntry(system_subtype="process"),
            LocationTypeSubtypeEntry(system_subtype="manufacture"),
            LocationTypeSubtypeEntry(system_subtype="culture"),
            LocationTypeSubtypeEntry(system_subtype="farm"),
            LocationTypeSubtypeEntry(system_subtype="livestock"),
        ],
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

_CANONICAL_ENTRIES: tuple[LocationTypeEntry, ...] = tuple(
    entry.fixture_identity() for entry in _ENGINE_ENTRIES
)


class WorldLocationTypeRegistry(RootModel[list[LocationTypeEntry]]):
    """Root POJO for `worlds.location_type_registry`. Wire shape: JSON array (map normalized on import)."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-LOC-TYPE"
    SYSTEM_TYPE_SETTLEMENT: ClassVar[str] = "settlement"
    SYSTEM_TYPE_DISTRICT: ClassVar[str] = "district"
    SYSTEM_TYPE_BUILDING: ClassVar[str] = "building"

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

    def merged_with_engine(self) -> WorldLocationTypeRegistry:
        """Engine hierarchy + recipes; world types/subtypes overlay by key (CITY-T-2d)."""
        engine = type(self).canonical_engine()
        world_by_type = {entry.system_type: entry for entry in self.root}
        merged: list[LocationTypeEntry] = []
        seen: set[str] = set()
        for engine_entry in engine.root:
            world_entry = world_by_type.get(engine_entry.system_type)
            if world_entry is None:
                merged.append(engine_entry)
            else:
                merged.append(_overlay_location_type(engine_entry, world_entry))
            seen.add(engine_entry.system_type)
        for world_entry in self.root:
            if world_entry.system_type not in seen:
                merged.append(world_entry)
        return WorldLocationTypeRegistry(merged)


def _overlay_location_type(
    engine: LocationTypeEntry,
    world: LocationTypeEntry,
) -> LocationTypeEntry:
    parent_types = world.parent_types if world.parent_types else engine.parent_types
    is_outdoor = engine.is_outdoor if world.is_outdoor is None else world.is_outdoor
    if not world.subtypes:
        subtypes = list(engine.subtypes)
    else:
        by_sub = {subtype.system_subtype: subtype for subtype in engine.subtypes}
        for subtype in world.subtypes:
            by_sub[subtype.system_subtype] = _overlay_subtype(
                by_sub.get(subtype.system_subtype), subtype,
            )
        subtypes = list(by_sub.values())
    return LocationTypeEntry(
        system_type=world.system_type,
        display_type=world.display_type,
        parent_types=list(parent_types),
        is_outdoor=is_outdoor,
        subtypes=subtypes,
    )


def _overlay_subtype(
    engine: LocationTypeSubtypeEntry | None,
    world: LocationTypeSubtypeEntry,
) -> LocationTypeSubtypeEntry:
    if engine is None:
        return world
    return LocationTypeSubtypeEntry(
        system_subtype=world.system_subtype,
        display_subtype=(
            world.display_subtype if world.display_subtype is not None else engine.display_subtype
        ),
        border_category=(
            world.border_category if world.border_category is not None else engine.border_category
        ),
        l0_map_symbol=(
            world.l0_map_symbol if world.l0_map_symbol is not None else engine.l0_map_symbol
        ),
        typical_district_types=list(world.typical_district_types),
        required_structure_types=list(world.required_structure_types),
    )
