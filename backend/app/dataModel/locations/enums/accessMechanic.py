"""Closed access mechanics shared by levels and transitions (transitions §2/K9)."""

from enum import StrEnum


class AccessMechanic(StrEnum):
    LOCKPICK = "lockpick"
    KEY = "key"
    CLIMBING = "climbing"
    GUARD = "guard"
    EXCAVATION = "excavation"
    TELEPORT = "teleport"
