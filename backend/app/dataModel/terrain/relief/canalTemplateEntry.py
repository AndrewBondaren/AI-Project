"""One ``worlds.canal_template_registry[]`` row — tz_terrain_relief R36q."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class CanalStructureSpec(BaseModel):
    """Built/lined canal materials — refs → ``barrier_template_registry``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    structure_refs: DefaultOnWire[list[str]] = Field(default_factory=list)


class CanalTemplateEntry(BaseModel):
    """Reusable canal description on the world (not inlined on every grade case)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_type: StrictOnWire[str]
    earthen_canal: DefaultOnWire[bool | None] = None
    structure: DefaultOnWire[CanalStructureSpec | None] = None
