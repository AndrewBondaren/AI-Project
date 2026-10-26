"""``ReliefGradeInstance`` — one constant-angle grade object (R36j / §8c).

Analogous to one mountain peak. Cell holds only ``system_grade_uid``.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultEnumWhenMissing, DefaultWhenMissing
from app.dataModel.terrain.relief.enums import ReliefSideKind


class ReliefGradeInstance(BaseModel):
    """Composite grade: kind/h/L/angle once; ``cell_refs`` ↔ cell uid."""

    SCHEMA_ID: ClassVar[str] = "SCH-RELIEF-GRADE-INSTANCE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    grade_uid: str
    world_uid: str
    kind: DefaultEnumWhenMissing[ReliefSideKind]
    height_cells: int = Field(ge=1)
    length_cells: int = Field(ge=1)
    # light-grid (lx, ly) membership — omit empty not allowed (must have cells)
    cell_refs: list[tuple[int, int]] = Field(min_length=1)
    angle_deg: DefaultWhenMissing[float | None] = None
    facing: DefaultWhenMissing[str | None] = None
    earthen_canal: DefaultWhenMissing[bool] = False
    # Resolved canal attachments (R28/R36q); BAR-1 consumes structure_refs
    structure_refs: DefaultWhenMissing[list[str]] = Field(default_factory=list)
    structure_canal: DefaultWhenMissing[str | None] = None
    template_uid: DefaultWhenMissing[str | None] = None
    # Ribbon owner: connection edge uid. Omit when the front has no graph owner.
    owner_uid: DefaultWhenMissing[str | None] = None
    site_id: DefaultWhenMissing[str | None] = None
    grade_system_uid: DefaultWhenMissing[str | None] = None

    @model_validator(mode="after")
    def _kind_angle_facing(self) -> ReliefGradeInstance:
        if self.kind is ReliefSideKind.SHEER:
            if self.angle_deg is None:
                raise ValueError("SHEER grade requires honest angle_deg")
            if self.facing is not None and self.facing != "none":
                raise ValueError("SHEER grade facing must be omit or 'none'")
        elif self.kind is ReliefSideKind.SLOPE and self.angle_deg is None:
            raise ValueError("SLOPE grade requires angle_deg")
        return self
