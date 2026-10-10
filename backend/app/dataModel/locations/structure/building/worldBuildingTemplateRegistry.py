"""Root POJO for `worlds.building_template_registry` — heterogeneous column.

tz_building_generator §5.2: two row kinds discriminated by the
``system_template_uid`` key — uid pointers (``BuildingTemplateRegistryEntry``)
and embedded world-override plot layouts (``PlotLayoutTemplate``, interim
CITY-T-2b/5o). Readers go through ``pointers`` / ``layouts`` — never
discriminate by hand.
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Union

from pydantic import Discriminator, RootModel, Tag

from app.dataModel.locations.structure.building.buildingTemplateRegistryEntry import (
    BuildingTemplateRegistryEntry,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
)


def _row_tag(row: Any) -> str:
    """Discriminator of §5.2: a row carrying ``system_template_uid`` is a
    uid pointer — the same rule as ``worldRow`` overrides and pack remap.

    Validation feeds raw dicts; serialization feeds model instances —
    both are tagged here so the union never serializes a pointer entry
    through the layout member.
    """
    if isinstance(row, BuildingTemplateRegistryEntry):
        return "pointer"
    if isinstance(row, PlotLayoutTemplate):
        return "layout"
    if isinstance(row, dict) and "system_template_uid" in row:
        return "pointer"
    return "layout"


BuildingRegistryRow = Annotated[
    Union[
        Annotated[BuildingTemplateRegistryEntry, Tag("pointer")],
        Annotated[PlotLayoutTemplate, Tag("layout")],
    ],
    Discriminator(_row_tag),
]
"""One ``building_template_registry[]`` row — uid pointer or embedded layout."""


class WorldBuildingTemplateRegistry(RootModel[list[BuildingRegistryRow]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-BUILDING-TEMPLATE"

    root: list[BuildingRegistryRow]

    @property
    def pointers(self) -> list[BuildingTemplateRegistryEntry]:
        """Uid-pointer rows — the library-binding view of the column."""
        return [
            row
            for row in self.root
            if isinstance(row, BuildingTemplateRegistryEntry)
        ]

    @property
    def layouts(self) -> list[PlotLayoutTemplate]:
        """Embedded world-override plot layouts (interim, CITY-T-2b/5o)."""
        return [row for row in self.root if isinstance(row, PlotLayoutTemplate)]

    @classmethod
    def canonical_defaults(cls) -> WorldBuildingTemplateRegistry:
        return cls([])
