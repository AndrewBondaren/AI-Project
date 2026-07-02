"""Root POJO for `worlds.city_size_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.settlement.settlement.citySizeEntry import CitySizeEntry

_CANONICAL_ENTRIES: tuple[CitySizeEntry, ...] = (
    CitySizeEntry(system_size="hamlet", display_size="Хутор", map_cells_count=1, footprint_multiplier=0.25),
    CitySizeEntry(system_size="village", display_size="Деревня", map_cells_count=2, footprint_multiplier=0.5),
    CitySizeEntry(system_size="town", display_size="Городок", map_cells_count=4, footprint_multiplier=1.0),
    CitySizeEntry(system_size="city", display_size="Город", map_cells_count=9, footprint_multiplier=2.0),
    CitySizeEntry(system_size="metropolis", display_size="Метрополис", map_cells_count=20, footprint_multiplier=4.0),
    CitySizeEntry(system_size="megalopolis", display_size="Мегалополис", map_cells_count=50, footprint_multiplier=8.0),
)


class WorldCitySizeRegistry(RootModel[list[CitySizeEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-CITY-SIZE"
    root: list[CitySizeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldCitySizeRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_size: str) -> CitySizeEntry | None:
        for entry in self.root:
            if entry.system_size == system_size:
                return entry
        return None

    @classmethod
    def footprint_multiplier_defaults(cls) -> dict[str, float]:
        return {
            entry.system_size: float(entry.footprint_multiplier)
            for entry in cls.canonical_defaults().root
            if entry.footprint_multiplier is not None
        }
