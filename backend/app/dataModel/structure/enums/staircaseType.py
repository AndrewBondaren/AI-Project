"""Wire `staircase_type` keys and builtin shaft defaults — tz_building_generator.md §3.9."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class StaircaseTypeSpec:
    default_shaft_size_type: str
    requires_shaft: bool = True


class StaircaseType(StrEnum):
    STRAIGHT = "straight"
    U_SHAPE = "u_shape"
    SPIRAL = "spiral"
    VERTICAL_LADDER = "vertical_ladder"
    EXTERNAL_VERTICAL_LADDER = "external_vertical_ladder"

    @classmethod
    def from_wire(cls, key: str) -> StaircaseType | None:
        norm = (key or "").strip().lower()
        legacy = _LEGACY_WIRE_ALIASES.get(norm)
        if legacy is not None:
            return legacy
        for member in cls:
            if member.value == norm:
                return member
        return None


_LEGACY_WIRE_ALIASES: dict[str, StaircaseType] = {
    "trapdoor": StaircaseType.VERTICAL_LADDER,
}


_SPECS: dict[StaircaseType, StaircaseTypeSpec] = {
    StaircaseType.STRAIGHT: StaircaseTypeSpec(default_shaft_size_type="standard"),
    StaircaseType.U_SHAPE: StaircaseTypeSpec(default_shaft_size_type="sq_small"),
    StaircaseType.SPIRAL: StaircaseTypeSpec(default_shaft_size_type="spiral_3"),
    StaircaseType.VERTICAL_LADDER: StaircaseTypeSpec(
        default_shaft_size_type="sq_small",
        requires_shaft=False,
    ),
    StaircaseType.EXTERNAL_VERTICAL_LADDER: StaircaseTypeSpec(
        default_shaft_size_type="sq_small",
        requires_shaft=False,
    ),
}

# Legacy wire alias: staircase_type "standard" → straight size preset key.
_STAIRCASE_TYPE_SIZE_ALIASES: dict[str, str] = {
    "standard": "standard",
}

_FALLBACK_SHAFT_SIZE_TYPE = "sq_small"


def requires_shaft(staircase_type: str) -> bool:
    member = StaircaseType.from_wire(staircase_type)
    if member is None:
        return True
    return _SPECS[member].requires_shaft


def default_shaft_size_type(staircase_type: str) -> str:
    alias = _STAIRCASE_TYPE_SIZE_ALIASES.get((staircase_type or "").strip().lower())
    if alias is not None:
        return alias
    member = StaircaseType.from_wire(staircase_type)
    if member is not None:
        return _SPECS[member].default_shaft_size_type
    return _FALLBACK_SHAFT_SIZE_TYPE


def no_shaft_types() -> frozenset[StaircaseType]:
    return frozenset(
        member for member, spec in _SPECS.items() if not spec.requires_shaft
    )
