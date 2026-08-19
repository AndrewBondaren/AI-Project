"""Outgoing rim ray — debug consume leftover, not SQL and not a pack column.

SoT: ``docs/tz_terrain_relief_consume.md``. Identity = ``(cell, Facing)`` (C41).
``kind`` chooses the edge glyph (SLOPE arrow / SHEER bar).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefSideKind


class GradeRimRay(BaseModel):
    """One claimed outgoing ray from a rim cell (world XY)."""

    SCHEMA_ID: ClassVar[str] = "SCH-GRADE-RIM-RAY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    x: int
    y: int
    facing: Facing
    kind: ReliefSideKind

    @property
    def cell(self) -> tuple[int, int]:
        return (int(self.x), int(self.y))


class GradeRaySidecar(BaseModel):
    """Debug sidecar on disk (tile or location). Not FineTerrain, not catalog SQL."""

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
