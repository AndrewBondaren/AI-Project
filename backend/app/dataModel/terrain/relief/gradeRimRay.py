"""Grade rim edge slots in pack — sender (C41) + receiver (opposite).

SoT: ``docs/tz_terrain_relief_consume.md``. C41 identity = sender ``(cell, Facing)``.
Receiver is persist, not a second claim and not render ``opposite``.
``kind`` chooses the edge glyph (SLOPE arrow / SHEER bar). Default ``SLOPE``
when the slot is not a painted leftover front (equal-z body / no Instance).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.spatial.facing import Facing, GRID_OUTWARD_DELTA, opposite
from app.dataModel.terrain.relief.enums import ReliefSideKind


class GradeRimRay(BaseModel):
    """One pack slot: sender C41 leftover or derived receiver (world XY)."""

    SCHEMA_ID: ClassVar[str] = "SCH-GRADE-RIM-RAY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    x: int
    y: int
    facing: Facing
    kind: ReliefSideKind = Field(
        default=ReliefSideKind.SLOPE,
        description="Glyph; omit when no painted front — not an Instance kind.",
    )

    @property
    def cell(self) -> tuple[int, int]:
        return (int(self.x), int(self.y))


class GradeRaySidecar(BaseModel):
    """Pack file (tile or location): slot rays. Not FineTerrain, not catalog SQL."""

    SCHEMA_ID: ClassVar[str] = "SCH-GRADE-RAY-SIDECAR"

    model_config = ConfigDict(extra="ignore", frozen=True)

    rays: tuple[GradeRimRay, ...] = Field(default_factory=tuple)


def merge_grade_rim_rays(*groups: Iterable[GradeRimRay]) -> tuple[GradeRimRay, ...]:
    """Last-wins on ``(x, y, facing)`` — same uniqueness as C41 claim."""
    by_key: dict[tuple[int, int, Facing], GradeRimRay] = {}
    for group in groups:
        for ray in group:
            by_key[(int(ray.x), int(ray.y), ray.facing)] = ray
    return tuple(by_key.values())


def receiver_rim_ray(sender: GradeRimRay) -> GradeRimRay:
    """Hit cell + ``opposite`` facing; same kind. Not a second C41 claim."""
    dx, dy = GRID_OUTWARD_DELTA[sender.facing]
    return GradeRimRay(
        x=int(sender.x) + int(dx),
        y=int(sender.y) + int(dy),
        facing=opposite(sender.facing),
        kind=sender.kind,
    )


def pack_rim_slot_rays(
    senders: Iterable[GradeRimRay],
    *,
    cells: Collection[tuple[int, int]],
) -> tuple[GradeRimRay, ...]:
    """Sender slots plus receivers whose cell exists in this bake (TZ omit)."""
    allowed = {(int(x), int(y)) for x, y in cells}
    out: list[GradeRimRay] = []
    for sender in senders:
        out.append(sender)
        recv = receiver_rim_ray(sender)
        if recv.cell in allowed:
            out.append(recv)
    return merge_grade_rim_rays(out)
