"""Root POJO for `worlds.settlement_size_registry` — ranks ``small`` / ``medium`` / ``large``."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.registryKey import RegistryKey
from app.dataModel.settlement.settlement import settlementSizeEntry as _size_entry_mod
from app.dataModel.settlement.settlement.settlementSizeEntry import SettlementSizeEntry


class WorldSettlementSizeRegistry(RootModel[list[SettlementSizeEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-SETTLEMENT-SIZE"
    RUNTIME_MERGE_ID_FIELD: ClassVar[str] = "system_size"
    root: list[SettlementSizeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldSettlementSizeRegistry:
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def default_system_size(cls) -> RegistryKey[WorldSettlementSizeRegistry]:
        """Omit rank on settlement-like → this canonical key (TZ LOC-T-2)."""
        return _CANONICAL_MEDIUM.system_size

    def entry_for(self, system_size: str) -> SettlementSizeEntry | None:
        for entry in self.root:
            if entry.system_size == system_size:
                return entry
        return None

    def resolve_system_size(self, system_size: str | None) -> RegistryKey[WorldSettlementSizeRegistry]:
        """Omit/blank/unknown → canonical medium. Lookup only; logging is jsonValidation."""
        key = (system_size or "").strip()
        if not key:
            return type(self).default_system_size()
        found = self.entry_for(key)
        if found is not None:
            return found.system_size
        return type(self).default_system_size()

    def rank(self, system_size: str | None) -> int:
        """Index in resolved ``root``. Omit → default rank. Unknown → ``-1``."""
        key = (system_size or "").strip() or type(self).default_system_size()
        for index, entry in enumerate(self.root):
            if entry.system_size == key:
                return index
        return -1


type SettlementSizeKey = RegistryKey[WorldSettlementSizeRegistry]

_size_entry_mod.WorldSettlementSizeRegistry = WorldSettlementSizeRegistry
SettlementSizeEntry.model_rebuild()

_CANONICAL_SMALL = SettlementSizeEntry(system_size="small", display_size="Малый")
_CANONICAL_MEDIUM = SettlementSizeEntry(system_size="medium", display_size="Средний")
_CANONICAL_LARGE = SettlementSizeEntry(system_size="large", display_size="Большой")
_CANONICAL_ENTRIES: tuple[SettlementSizeEntry, ...] = (
    _CANONICAL_SMALL,
    _CANONICAL_MEDIUM,
    _CANONICAL_LARGE,
)
