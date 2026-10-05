"""Closed engine transition vocabulary and behavior — tz_location_transitions §3.1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TransitionVertical(StrEnum):
    """Vertical geometry classification; ANY permits horizontal or vertical endpoints."""

    NONE = "none"
    REQUIRED = "required"
    ANY = "any"
    DOWN = "down"


@dataclass(frozen=True)
class TransitionTypeSpec:
    entry: bool
    directional: bool
    vertical: TransitionVertical


class TransitionType(StrEnum):
    MAIN_ENTRANCE = "main_entrance"
    SERVICE_ENTRANCE = "service_entrance"
    HIDDEN_ENTRANCE = "hidden_entrance"
    DOOR = "door"
    DOORWAY = "doorway"
    ARCHWAY = "archway"
    CORRIDOR = "corridor"
    STAIRCASE = "staircase"
    LADDER = "ladder"
    ROPE = "rope"
    HATCH = "hatch"
    TUNNEL = "tunnel"
    GATE = "gate"
    BREACH = "breach"
    BRIDGE = "bridge"
    PORTAL = "portal"
    FALL = "fall"

    @property
    def spec(self) -> TransitionTypeSpec:
        return _SPECS[self]

    @property
    def entry(self) -> bool:
        return self.spec.entry

    @property
    def directional(self) -> bool:
        return self.spec.directional

    @property
    def vertical(self) -> TransitionVertical:
        return self.spec.vertical


_SPECS: dict[TransitionType, TransitionTypeSpec] = {
    TransitionType.MAIN_ENTRANCE: TransitionTypeSpec(True, False, TransitionVertical.NONE),
    TransitionType.SERVICE_ENTRANCE: TransitionTypeSpec(True, False, TransitionVertical.NONE),
    TransitionType.HIDDEN_ENTRANCE: TransitionTypeSpec(True, False, TransitionVertical.ANY),
    TransitionType.DOOR: TransitionTypeSpec(False, False, TransitionVertical.NONE),
    TransitionType.DOORWAY: TransitionTypeSpec(False, False, TransitionVertical.NONE),
    TransitionType.ARCHWAY: TransitionTypeSpec(False, False, TransitionVertical.NONE),
    TransitionType.CORRIDOR: TransitionTypeSpec(False, False, TransitionVertical.NONE),
    TransitionType.STAIRCASE: TransitionTypeSpec(False, False, TransitionVertical.REQUIRED),
    TransitionType.LADDER: TransitionTypeSpec(False, False, TransitionVertical.REQUIRED),
    TransitionType.ROPE: TransitionTypeSpec(False, False, TransitionVertical.REQUIRED),
    TransitionType.HATCH: TransitionTypeSpec(False, False, TransitionVertical.REQUIRED),
    TransitionType.TUNNEL: TransitionTypeSpec(False, False, TransitionVertical.ANY),
    TransitionType.GATE: TransitionTypeSpec(False, False, TransitionVertical.NONE),
    TransitionType.BREACH: TransitionTypeSpec(False, False, TransitionVertical.ANY),
    TransitionType.BRIDGE: TransitionTypeSpec(False, False, TransitionVertical.NONE),
    TransitionType.PORTAL: TransitionTypeSpec(False, True, TransitionVertical.ANY),
    TransitionType.FALL: TransitionTypeSpec(False, True, TransitionVertical.DOWN),
}

if set(_SPECS) != set(TransitionType):
    raise RuntimeError("TransitionType metadata must cover every builtin")
