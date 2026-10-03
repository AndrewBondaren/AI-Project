"""Root POJO for `worlds.location_mood_registry`."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.registryKey import RegistryKey
import app.dataModel.settlement.settlement.locationMoodEntry as _entry_mod
from app.dataModel.settlement.settlement.locationMoodEntry import LocationMoodEntry


class WorldLocationMoodRegistry(RootModel[list[LocationMoodEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-LOC-MOOD"

    root: list[LocationMoodEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldLocationMoodRegistry:
        return cls(list(_CANONICAL_ENTRIES))


type LocationMoodKey = RegistryKey[WorldLocationMoodRegistry]

_entry_mod.WorldLocationMoodRegistry = WorldLocationMoodRegistry
LocationMoodEntry.model_rebuild()

_CANONICAL_ENTRIES: tuple[LocationMoodEntry, ...] = (
    LocationMoodEntry(system_mood="prosperous", display_mood="Процветающий"),
    LocationMoodEntry(system_mood="declining", display_mood="Приходящий в упадок"),
    LocationMoodEntry(system_mood="militarized", display_mood="Милитаризованный"),
    LocationMoodEntry(system_mood="mysterious", display_mood="Таинственный"),
    LocationMoodEntry(system_mood="dangerous", display_mood="Опасный"),
    LocationMoodEntry(system_mood="abandoned", display_mood="Заброшенный"),
)
