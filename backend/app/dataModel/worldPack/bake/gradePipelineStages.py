"""Outdoor grade mill/paint stages — one contract for bake and on-demand chunk refine.

Product default is off (player launch must not wait). Paint without mill is coerced off.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator


class GradePipelineStages(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-GRADE-PIPELINE-STAGES"

    model_config = ConfigDict(extra="ignore", frozen=True)

    mill: bool = False
    paint: bool = False

    @model_validator(mode="before")
    @classmethod
    def _paint_requires_mill(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        mill = bool(data.get("mill", False))
        paint = bool(data.get("paint", False))
        if paint and not mill:
            return {**data, "paint": False}
        return data

    @classmethod
    def off(cls) -> GradePipelineStages:
        return cls(mill=False, paint=False)

    @classmethod
    def full(cls) -> GradePipelineStages:
        return cls(mill=True, paint=True)
