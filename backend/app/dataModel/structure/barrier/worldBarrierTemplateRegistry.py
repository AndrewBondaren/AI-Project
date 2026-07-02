"""Root POJO for `worlds.barrier_template_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.structure.barrier.barrierTemplateEntry import BarrierTemplateEntry
from app.dataModel.shared.ranges import IntMinMax
from app.dataModel.structure.materialPick import MaterialPick

_CANONICAL_ENTRIES: tuple[BarrierTemplateEntry, ...] = (
    BarrierTemplateEntry(
        system_type="wooden_fence",
        glossary_ref="barrier_wooden_fence",
        wall_material=MaterialPick(pick_from=["wood"]),
        height_levels=IntMinMax(min=1, max=1),
        gates=IntMinMax(min=1, max=2),
    ),
    BarrierTemplateEntry(
        system_type="stone_fence",
        glossary_ref="barrier_stone_fence",
        wall_material=MaterialPick(pick_from=["stone"]),
        height_levels=IntMinMax(min=1, max=2),
        gates=IntMinMax(min=1, max=4),
    ),
    BarrierTemplateEntry(
        system_type="city_wall",
        glossary_ref="barrier_city_wall",
        wall_material=MaterialPick(pick_from=["stone"]),
        height_levels=IntMinMax(min=2, max=5),
        gates=IntMinMax(min=1, max=6),
        towers=IntMinMax(min=0, max=20),
    ),
)


class WorldBarrierTemplateRegistry(RootModel[list[BarrierTemplateEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-BARRIER-TEMPLATE"
    root: list[BarrierTemplateEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldBarrierTemplateRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    def entry_for(self, system_type: str) -> BarrierTemplateEntry | None:
        for entry in self.root:
            if entry.system_type == system_type:
                return entry
        return None
