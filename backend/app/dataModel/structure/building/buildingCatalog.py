"""Sync snapshot of generate-able building layouts for one settlement assembly.

CITY-T-2b. Not live SQL — caller hydrates, then passes this into assemblers.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate


class BuildingCatalog:
    """``layouts`` unique by ``system_name`` (later wins). Ordered by ``system_name``."""

    def __init__(self, layouts: Iterable[BuildingLayoutTemplate]) -> None:
        by_name: dict[str, BuildingLayoutTemplate] = {}
        for layout in layouts:
            by_name[layout.system_name] = layout
        self._by_name = {name: by_name[name] for name in sorted(by_name)}
        self.layouts: tuple[BuildingLayoutTemplate, ...] = tuple(self._by_name.values())

    @classmethod
    def from_layouts(cls, layouts: Iterable[BuildingLayoutTemplate]) -> BuildingCatalog:
        return cls(layouts)

    @classmethod
    def empty(cls) -> BuildingCatalog:
        return cls(())

    def by_system_name(self, name: str) -> BuildingLayoutTemplate | None:
        return self._by_name.get(name)

    def of_structure_type(self, structure_type: str) -> tuple[BuildingLayoutTemplate, ...]:
        return tuple(
            layout for layout in self.layouts if layout.structure_type == structure_type
        )

    def structure_types(self) -> tuple[str, ...]:
        return tuple(sorted({layout.structure_type for layout in self.layouts}))
