"""Root POJO for ``worlds.canal_template_registry`` — tz_terrain_relief R36q."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.terrain.relief.canalTemplateEntry import CanalTemplateEntry


class WorldCanalTemplateRegistry(RootModel[list[CanalTemplateEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-CANAL-TEMPLATE"
    root: list[CanalTemplateEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldCanalTemplateRegistry:
        return cls([])

    def entry_for(self, system_type: str) -> CanalTemplateEntry | None:
        key = str(system_type)
        for entry in self.root:
            if entry.system_type == key:
                return entry
        return None
