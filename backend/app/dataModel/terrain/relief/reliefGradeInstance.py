"""``ReliefGradeInstance`` — one constant-angle grade object (R36j / §8c).

Analogous to one mountain peak. Cell holds only ``system_grade_uid``.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultEnumOnWire, DefaultOnWire
from app.dataModel.terrain.relief.enums import ReliefSideKind


class ReliefGradeInstance(BaseModel):
    """Composite grade: kind/h/L/angle once; ``cell_refs`` ↔ cell uid."""

    SCHEMA_ID: ClassVar[str] = "SCH-RELIEF-GRADE-INSTANCE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    grade_uid: str
    world_uid: str
    kind: DefaultEnumOnWire[ReliefSideKind]
    height_cells: int = Field(ge=1)
    length_cells: int = Field(ge=1)
    # light-grid (lx, ly) membership — omit empty not allowed (must have cells)
    cell_refs: list[tuple[int, int]] = Field(min_length=1)
    angle_deg: DefaultOnWire[float | None] = None
    facing: DefaultOnWire[str | None] = None
    earthen_canal: DefaultOnWire[bool] = False
    # Resolved canal attachments (R28/R36q); BAR-1 consumes structure_refs
    structure_refs: DefaultOnWire[list[str]] = Field(default_factory=list)
    structure_canal: DefaultOnWire[str | None] = None
    template_uid: DefaultOnWire[str | None] = None
    edge_uid: DefaultOnWire[str | None] = None
    site_id: DefaultOnWire[str | None] = None
    grade_system_uid: DefaultOnWire[str | None] = None

    @model_validator(mode="after")
    def _sheer_omits_angle_facing(self) -> ReliefGradeInstance:
        if self.kind is ReliefSideKind.SHEER:
            if self.angle_deg is not None:
                raise ValueError("SHEER grade must omit angle_deg (R36e)")
            if self.facing is not None and self.facing != "none":
                raise ValueError("SHEER grade facing must be omit or 'none'")
        elif self.kind is ReliefSideKind.SLOPE and self.angle_deg is None:
            raise ValueError("SLOPE grade requires angle_deg")
        return self
