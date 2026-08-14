"""L0 AABB wrap copy — which world-map wire fields the seam writes."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class WorldSeamCopy(BaseModel):
    """Owner-rim snapshot applied to the antagonist rim (not hydro/climate/grade)."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-SEAM-COPY"
    model_config = ConfigDict(extra="forbid", frozen=True)

    surface_z: int
    system_terrain: str | None = None
