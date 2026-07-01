"""Root POJO for `worlds.location_mood_registry`."""

from __future__ import annotations

from pydantic import RootModel

from app.dataModel.settlement.settlement.locationMoodEntry import LocationMoodEntry

_CANONICAL_ENTRIES: tuple[LocationMoodEntry, ...] = (
    LocationMoodEntry(system_mood="prosperous", display_mood="Процветающий"),
    LocationMoodEntry(system_mood="declining", display_mood="Приходящий в упадок"),
    LocationMoodEntry(system_mood="militarized", display_mood="Милитаризованный"),
    LocationMoodEntry(system_mood="mysterious", display_mood="Таинственный"),
    LocationMoodEntry(system_mood="dangerous", display_mood="Опасный"),
    LocationMoodEntry(system_mood="abandoned", display_mood="Заброшенный"),
)


class WorldLocationMoodRegistry(RootModel[list[LocationMoodEntry]]):
    root: list[LocationMoodEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldLocationMoodRegistry:
        return cls(list(_CANONICAL_ENTRIES))
