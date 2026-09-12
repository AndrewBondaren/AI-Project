"""BuildingPurposeFamily — parent of plot purpose leaves. Not a drawing tag."""

from __future__ import annotations

from enum import StrEnum


class BuildingPurposeFamily(StrEnum):
    """Род функции. Не ткань района (``civic`` / ``commercial``)."""

    DWELLING = "dwelling"
    PUBLIC = "public"
    GOVERNMENT = "government"
    KNOWLEDGE = "knowledge"
    DIPLOMATIC = "diplomatic"
    TRADE = "trade"
    CRAFT = "craft"
    FACTORY = "factory"
    EXTRACT = "extract"
    PROCESS = "process"
    AGRARIAN = "agrarian"
    UTILITY = "utility"
    DEFENSE = "defense"
    HARBOR = "harbor"
    TRANSIT = "transit"

    @classmethod
    def from_wire(cls, key: object) -> BuildingPurposeFamily | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        if not norm:
            return None
        for member in cls:
            if member.value == norm:
                return member
        return None
