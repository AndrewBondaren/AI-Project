"""Root POJO for ``worlds.relief_template_registry``."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.terrain.relief.reliefTemplateRegistryEntry import (
    ReliefTemplateRegistryEntry,
)


class WorldReliefTemplateRegistry(RootModel[list[ReliefTemplateRegistryEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-RELIEF-TEMPLATE"

    root: list[ReliefTemplateRegistryEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldReliefTemplateRegistry:
        return cls([])

    def entries_for_context(self, context: str) -> list[ReliefTemplateRegistryEntry]:
        return [e for e in self.root if e.context.value == context]

    def entry_for_uid(self, uid: str) -> ReliefTemplateRegistryEntry | None:
        for entry in self.root:
            if entry.system_template_uid == uid:
                return entry
        return None
