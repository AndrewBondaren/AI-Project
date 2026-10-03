"""One rigid rotation of generated runtime geometry, before layout assembly."""

from dataclasses import dataclass

from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.dataModel.spatial.facing import (
    CARDINAL_FACINGS, COMPACT_LETTER, GRID_DELTA_TO_FACING, GRID_OUTWARD_DELTA,
    Facing, parse_facing,
)
from app.dataModel.locations.structure.enums.passageType import PassageType
from app.dataModel.locations.structure.enums.attachWall import AttachWall
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell


@dataclass(frozen=True)
class StructureOrientation:
    pivot: tuple[int, int]
    quarter_turns: int

    def __post_init__(self):
        if self.quarter_turns not in range(4):
            raise ValueError("quarter_turns must be 0..3")

    def vector(self, x: int, y: int) -> tuple[int, int]:
        for _ in range(self.quarter_turns):
            x, y = -y, x
        return x, y

    def point(self, x: int, y: int) -> tuple[int, int]:
        dx, dy = self.vector(x - self.pivot[0], y - self.pivot[1])
        return self.pivot[0] + dx, self.pivot[1] + dy

    def inverse_point(self, x: int, y: int) -> tuple[int, int]:
        return StructureOrientation(self.pivot, -self.quarter_turns % 4).point(x, y)

    def facing(self, value: Facing | str) -> Facing:
        return GRID_DELTA_TO_FACING[self.vector(*GRID_OUTWARD_DELTA[parse_facing(value)])]

    def bbox(self, x: int, y: int, width: int, depth: int) -> tuple[int, int, int, int]:
        corners = [self.point(xx, yy) for xx in (x, x + width - 1) for yy in (y, y + depth - 1)]
        xs, ys = zip(*corners)
        return min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1

    def apply(self, cells: dict[tuple, MapCell], passages: list[LocationPassage], rooms: list[_RoomInstance]) -> None:
        if not self.quarter_turns:
            return
        rotated = {}
        for cell in cells.values():
            cell.x, cell.y = self.point(cell.x, cell.y)
            if cell.system_facing is not None:
                cell.system_facing = self.facing(cell.system_facing).value
            if cell.railing_sides is not None:
                cell.railing_sides = [
                    COMPACT_LETTER[self.facing(side)] if side in COMPACT_LETTER.values()
                    else self.facing(side).value for side in cell.railing_sides
                ]
            rotated[(cell.x, cell.y, cell.z)] = cell
        cells.clear()
        cells.update(rotated)
        for passage in passages:
            passage.to_x, passage.to_y = self.point(passage.to_x, passage.to_y)
            if passage.from_x is not None and passage.from_y is not None:
                passage.from_x, passage.from_y = self.point(passage.from_x, passage.from_y)
        for room in rooms:
            if not room.placed:
                continue
            room.origin_x, room.origin_y, room.width, room.depth = self.bbox(
                room.origin_x, room.origin_y, room.width, room.depth,
            )
            room.extra_cells = {self.point(x, y) for x, y in room.extra_cells}
            if room.entry_point is not None:
                room.entry_point = room.entry_point.model_copy(
                    update={"wall": self.facing(room.entry_point.wall)},
                )
            if room.back_entry_point is not None:
                room.back_entry_point = room.back_entry_point.model_copy(
                    update={"wall": self.facing(room.back_entry_point.wall)},
                )
            if room.is_shaft:
                if room.facing is not None:
                    room.facing = self.facing(room.facing).value
                if room.embedded_entry is not None:
                    room.embedded_entry = self.facing(room.embedded_entry)
            if room.attach_wall in CARDINAL_FACINGS:
                room.attach_wall = AttachWall(self.facing(room.attach_wall.value))


def validate_facing(facing: Facing | None, structure_uid: str) -> None:
    if facing is not None and facing not in CARDINAL_FACINGS:
        raise GenerationError(f"Structure '{structure_uid}': facing must be cardinal, got {facing!r}")


def entry_orientation(rooms: list[_RoomInstance], passages: list[LocationPassage], structure_uid: str, facing: Facing) -> StructureOrientation:
    """Resolve the author's entry wall and pivot from the placed entrance."""
    validate_facing(facing, structure_uid)
    candidates = [
        (room, entry) for room in rooms if room.placed
        for entry in (room.entry_point, room.back_entry_point)
        if entry is not None and entry.passage_type == PassageType.MAIN_ENTRANCE
    ]
    entrances = [p for p in passages if p.from_level_uid is None and p.system_passage_type == PassageType.MAIN_ENTRANCE]
    if len(candidates) != 1 or len(entrances) != 1:
        raise GenerationError(
            f"Structure '{structure_uid}': facing requires exactly one placed main_entrance; "
            f"room_id candidates={[r.room_id for r, _ in candidates]}, passages={len(entrances)}"
        )
    room, entry = candidates[0]
    wall = entry.wall
    validate_facing(wall, structure_uid)
    pivot = (room.origin_x, room.origin_y)
    for turns in range(4):
        orientation = StructureOrientation(pivot, turns)
        if orientation.facing(wall) == facing:
            return orientation
    raise GenerationError(f"Structure '{structure_uid}': cannot orient entry wall {wall!r}")
