"""Relief side Spec — tz_terrain_relief."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultEnumWhenMissing, DefaultWhenMissing
from app.dataModel.terrain.relief.enums import ReliefSideKind


class ReliefSideSpec(BaseModel):
    """One graded face: kind + SHEER ε band in light cells."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    kind: DefaultEnumWhenMissing[ReliefSideKind] = ReliefSideKind.SLOPE
    sheer_band_light: DefaultWhenMissing[int] = Field(default=1, ge=0)
