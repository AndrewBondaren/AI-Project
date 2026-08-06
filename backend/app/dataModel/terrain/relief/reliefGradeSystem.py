"""``ReliefGradeSystem`` — ≥2 grades with changing steepness (R36l / §8c).

Analogous to mountain range. One grade → no system row.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire


class ReliefGradeSystem(BaseModel):
    """Ordered chain of ``ReliefGradeInstance.grade_uid`` (len ≥ 2)."""

    SCHEMA_ID: ClassVar[str] = "SCH-RELIEF-GRADE-SYSTEM"

    model_config = ConfigDict(extra="ignore", frozen=True)

    grade_system_uid: str
    world_uid: str
    grade_instance_uids: list[str] = Field(min_length=2)
    # Ribbon owner: connection edge uid or context token (open_land / shore)
    owner_uid: DefaultOnWire[str | None] = None
    display_name: DefaultOnWire[str | None] = None
