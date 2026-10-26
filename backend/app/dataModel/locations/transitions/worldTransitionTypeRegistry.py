"""Typed transition vocabulary; no destination, arrival or traversal algorithms."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.locations.transitions import transitionTypeEntry as _entry_mod
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.locations.transitions.transitionTypeEntry import TransitionTypeEntry
from app.dataModel.registryKey import RegistryKey


class WorldTransitionTypeRegistry(RootModel[list[TransitionTypeEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-TRANSITION-TYPE"

    root: list[TransitionTypeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldTransitionTypeRegistry:
        return cls.canonical_engine()

    @classmethod
    def canonical_engine(cls) -> WorldTransitionTypeRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    def keys(self) -> frozenset[TransitionTypeKey]:
        return frozenset(entry.system_type for entry in self.root)

    def entry_for(self, system_type: str) -> TransitionTypeEntry | None:
        for entry in self.root:
            if entry.system_type == system_type:
                return entry
        return None

    def require(self, system_type: str) -> TransitionTypeKey:
        entry = self.entry_for(system_type)
        if entry is None:
            raise RuntimeError(f"WorldTransitionTypeRegistry missing {system_type!r}")
        return entry.system_type

    def type_for(self, system_type: str) -> TransitionType | None:
        entry = self.entry_for(system_type)
        return entry.behaves_as if entry is not None else None


type TransitionTypeKey = RegistryKey[WorldTransitionTypeRegistry]

_entry_mod.WorldTransitionTypeRegistry = WorldTransitionTypeRegistry
TransitionTypeEntry.model_rebuild()

_CANONICAL_ENTRIES: tuple[TransitionTypeEntry, ...] = tuple(
    TransitionTypeEntry(system_type=member, display_name=display, behaves_as=member)
    for member, display in (
        (TransitionType.MAIN_ENTRANCE, "Парадный вход"),
        (TransitionType.SERVICE_ENTRANCE, "Чёрный вход"),
        (TransitionType.HIDDEN_ENTRANCE, "Тайный вход"),
        (TransitionType.DOOR, "Дверь"),
        (TransitionType.DOORWAY, "Проём"),
        (TransitionType.ARCHWAY, "Арка"),
        (TransitionType.CORRIDOR, "Коридор"),
        (TransitionType.STAIRCASE, "Лестница"),
        (TransitionType.LADDER, "Стремянка"),
        (TransitionType.ROPE, "Верёвка"),
        (TransitionType.HATCH, "Люк"),
        (TransitionType.TUNNEL, "Тоннель"),
        (TransitionType.GATE, "Ворота периметра"),
        (TransitionType.BREACH, "Пролом"),
        (TransitionType.BRIDGE, "Мост"),
        (TransitionType.PORTAL, "Портал"),
        (TransitionType.FALL, "Провал"),
    )
)

if {entry.system_type for entry in _CANONICAL_ENTRIES} != set(TransitionType):
    raise RuntimeError("WorldTransitionTypeRegistry must list every builtin")
