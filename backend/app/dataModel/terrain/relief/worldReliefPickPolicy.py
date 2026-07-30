"""Pick policy per ReliefContext — tz_terrain_relief R19/R31."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


from app.dataModel.annotationPolicy import DefaultEnumOnWire, DefaultOnWire
from app.dataModel.terrain.relief.enums import ReliefPickMode


class ReliefContextPickPolicy(BaseModel):
    """One context: fixed requires default_template_uid."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    mode: DefaultEnumOnWire[ReliefPickMode] = ReliefPickMode.RANDOM
    default_template_uid: DefaultOnWire[str | None] = None

    @model_validator(mode="after")
    def _fixed_needs_uid(self) -> ReliefContextPickPolicy:
        if self.mode == ReliefPickMode.FIXED and not self.default_template_uid:
            raise ValueError("mode=fixed requires default_template_uid")
        return self


class WorldReliefPickPolicy(BaseModel):
    """``worlds.relief_pick_policy`` — defaults for all v1 contexts."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-RELIEF-PICK"
    model_config = ConfigDict(extra="ignore", frozen=True)

    mountain: DefaultOnWire[ReliefContextPickPolicy] = Field(
        default_factory=ReliefContextPickPolicy,
    )
    open_land: DefaultOnWire[ReliefContextPickPolicy] = Field(
        default_factory=ReliefContextPickPolicy,
    )
    shore: DefaultOnWire[ReliefContextPickPolicy] = Field(
        default_factory=ReliefContextPickPolicy,
    )
    road_shoulder: DefaultOnWire[ReliefContextPickPolicy] = Field(
        default_factory=ReliefContextPickPolicy,
    )

    @classmethod
    def canonical_defaults(cls) -> WorldReliefPickPolicy:
        return cls()

    def for_context(self, context: str) -> ReliefContextPickPolicy:
        return getattr(self, context)


class ObjectReliefPickPolicy(BaseModel):
    """Partial override on mountain Spec / connection edge (R31)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    mountain: DefaultOnWire[ReliefContextPickPolicy | None] = None
    open_land: DefaultOnWire[ReliefContextPickPolicy | None] = None
    shore: DefaultOnWire[ReliefContextPickPolicy | None] = None
    road_shoulder: DefaultOnWire[ReliefContextPickPolicy | None] = None

    def for_context(self, context: str) -> ReliefContextPickPolicy | None:
        return getattr(self, context)
