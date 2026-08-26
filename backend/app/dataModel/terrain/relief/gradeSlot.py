"""Pack cell-edge slot codes — tz_terrain_relief § Pack-слот.

Four IntEnums share a wire number line; they are not one enum (LLM/code
must not mix octant and seam). Glyphs are dump-only, not this module.
Mill ``Facing`` stays a StrEnum; convert only at the mill↔pack boundary.
Pair θ (80°, L=1) lives in ``gradeLeftoverPair``.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import IntEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.dataModel.spatial.facing import Facing, GRID_OUTWARD_DELTA, OPPOSITE

GRADE_SLOT_SCHEMA_ID = "SCH-GRADE-CELL-SLOTS"
GRADE_SLOT_COUNT = 8
GRADE_SLOT_CODE_MAX = 10


class GradeOctant(IntEnum):
    """SLOPE flow direction. Wire 0…7. Value is the flow, not the cell edge."""

    NORTHWEST = 0
    NORTH = 1
    NORTHEAST = 2
    WEST = 3
    EAST = 4
    SOUTHWEST = 5
    SOUTH = 6
    SOUTHEAST = 7

    def opposite(self) -> GradeOctant:
        return octant_from_facing(OPPOSITE[facing_from_octant(self)])

    def delta(self) -> tuple[int, int]:
        return GRID_OUTWARD_DELTA[facing_from_octant(self)]


class GradeSeam(IntEnum):
    """Edge with no neighbor in ``z_height_map``. Wire 8."""

    SEAM = 8


class GradeSheer(IntEnum):
    """Leftover SHEER both ends. Wire 9."""

    SHEER = 9


class GradeCouple(IntEnum):
    """Same-z coupling both ends. Wire 10."""

    COUPLE = 10


GradeSlotCode = GradeOctant | GradeSeam | GradeSheer | GradeCouple

_SLOT_CODE_ENUMS: tuple[type[IntEnum], ...] = (
    GradeOctant,
    GradeSeam,
    GradeSheer,
    GradeCouple,
)

_OCTANT_BY_FACING: dict[Facing, GradeOctant] = {
    Facing.NORTHWEST: GradeOctant.NORTHWEST,
    Facing.NORTH: GradeOctant.NORTH,
    Facing.NORTHEAST: GradeOctant.NORTHEAST,
    Facing.WEST: GradeOctant.WEST,
    Facing.EAST: GradeOctant.EAST,
    Facing.SOUTHWEST: GradeOctant.SOUTHWEST,
    Facing.SOUTH: GradeOctant.SOUTH,
    Facing.SOUTHEAST: GradeOctant.SOUTHEAST,
}
_FACING_BY_OCTANT: dict[GradeOctant, Facing] = {
    octant: facing for facing, octant in _OCTANT_BY_FACING.items()
}


def octant_from_facing(facing: Facing) -> GradeOctant:
    return _OCTANT_BY_FACING[facing]


def facing_from_octant(octant: GradeOctant) -> Facing:
    return _FACING_BY_OCTANT[octant]


def decode_grade_slot_code(code: int) -> GradeSlotCode:
    """Wire int → member. Raises ``ValueError`` outside 0…10."""
    value = int(code)
    for enum_cls in _SLOT_CODE_ENUMS:
        try:
            return enum_cls(value)  # type: ignore[return-value]
        except ValueError:
            continue
    raise ValueError(f"grade slot code must be 0..{GRADE_SLOT_CODE_MAX}; got {value}")


def neighbor_cell(xy: tuple[int, int], position: int) -> tuple[int, int]:
    """Cell at dump-edge ``position`` 0…7."""
    idx = int(position)
    if idx < 0 or idx >= GRADE_SLOT_COUNT:
        raise ValueError(f"slot position must be 0..7; got {idx}")
    dx, dy = GradeOctant(idx).delta()
    return (int(xy[0]) + dx, int(xy[1]) + dy)


class GradeCellSlots(BaseModel):
    """One occupancy cell: eight wire codes in dump-edge order."""

    SCHEMA_ID: ClassVar[str] = GRADE_SLOT_SCHEMA_ID

    model_config = ConfigDict(extra="ignore", frozen=True)

    x: int
    y: int
    slots: tuple[int, ...] = Field(min_length=GRADE_SLOT_COUNT, max_length=GRADE_SLOT_COUNT)

    @field_validator("slots")
    @classmethod
    def _codes_in_range(cls, slots: tuple[int, ...]) -> tuple[int, ...]:
        out: list[int] = []
        for raw in slots:
            code = int(raw)
            decode_grade_slot_code(code)
            out.append(code)
        return tuple(out)

    @property
    def cell(self) -> tuple[int, int]:
        return (int(self.x), int(self.y))

    def code_at(self, position: int) -> GradeSlotCode:
        idx = int(position)
        if idx < 0 or idx >= GRADE_SLOT_COUNT:
            raise ValueError(f"slot position must be 0..7; got {idx}")
        return decode_grade_slot_code(self.slots[idx])


class GradeSlotSidecar(BaseModel):
    """Pack sidecar body — ``docs/tz_terrain_relief_consume.md`` § Тело sidecar."""

    SCHEMA_ID: ClassVar[str] = GRADE_SLOT_SCHEMA_ID

    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_id: str = GRADE_SLOT_SCHEMA_ID
    cells: tuple[GradeCellSlots, ...] = Field(default_factory=tuple)

    @field_validator("schema_id")
    @classmethod
    def _known_schema(cls, value: str) -> str:
        if value != GRADE_SLOT_SCHEMA_ID:
            raise ValueError(f"schema_id must be {GRADE_SLOT_SCHEMA_ID}; got {value}")
        return value


def merge_grade_cell_slots(*groups: Iterable[GradeCellSlots]) -> tuple[GradeCellSlots, ...]:
    """First-wins on ``(x, y, position 0…7)``; emit complete cells only."""
    by_pos: dict[tuple[int, int, int], int] = {}
    order: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for group in groups:
        for cell in group:
            xy = (int(cell.x), int(cell.y))
            if xy not in seen:
                seen.add(xy)
                order.append(xy)
            for position, code in enumerate(cell.slots):
                key = (xy[0], xy[1], position)
                if key not in by_pos:
                    by_pos[key] = int(code)
    out: list[GradeCellSlots] = []
    for xy in order:
        slots = tuple(by_pos[(xy[0], xy[1], position)] for position in range(GRADE_SLOT_COUNT))
        if len(slots) != GRADE_SLOT_COUNT or any(
            (xy[0], xy[1], position) not in by_pos for position in range(GRADE_SLOT_COUNT)
        ):
            continue
        out.append(GradeCellSlots(x=xy[0], y=xy[1], slots=slots))
    return tuple(out)
