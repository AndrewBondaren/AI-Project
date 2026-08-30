"""Declared street-approach role — tz_settlement_outdoor.md C20."""

from __future__ import annotations

from enum import StrEnum


class EntryRole(StrEnum):
    FRONT = "front"
    SERVICE = "service"

    @classmethod
    def from_wire(cls, key: str | EntryRole | None) -> EntryRole | None:
        if key is None:
            return None
        if isinstance(key, cls):
            return key
        norm = str(key).strip().lower()
        for member in cls:
            if member.value == norm:
                return member
        return None
