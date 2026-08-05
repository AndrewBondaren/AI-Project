"""Pick policy per ReliefContext — tz_terrain_relief R19/R31."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


from app.dataModel.annotationPolicy import DefaultEnumOnWire, DefaultOnWire
from app.dataModel.terrain.relief.canalObstaclePolicy import CanalObstaclePolicyRule
from app.dataModel.terrain.relief.enums import CanalObstacleEntity, ReliefPickMode


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
    """``worlds.relief_pick_policy`` — defaults for all v1 contexts + R36p."""

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
    canal_obstacle_policy: DefaultOnWire[list[CanalObstaclePolicyRule]] = Field(
        default_factory=list,
    )

    @classmethod
    def canonical_defaults(cls) -> WorldReliefPickPolicy:
        return cls()

    def for_context(self, context: str) -> ReliefContextPickPolicy:
        return getattr(self, context)

    @model_validator(mode="after")
    def _canal_ref_overlap(self) -> WorldReliefPickPolicy:
        """True-rules matching same entity must share ``canal_ref`` (R36p / T-46)."""
        rules = self.canal_obstacle_policy
        if len(rules) < 2:
            return self
        # Check each concrete entity (+ synthetic probe for "all"-only conflicts)
        probes = [e for e in CanalObstacleEntity if e is not CanalObstacleEntity.ALL]
        for entity in probes:
            matched = [
                r for r in rules
                if CanalObstacleEntity.ALL in r.entities or entity in r.entities
            ]
            enabled = [r for r in matched if r.to_canal_cut_enable]
            if len(enabled) < 2:
                continue
            refs = {(r.canal_ref or "").strip() or None for r in enabled}
            refs.discard(None)
            if len(refs) > 1:
                raise ValueError(
                    "canal_obstacle_policy: conflicting canal_ref among "
                    f"enabled rules for entity={entity.value}: {sorted(refs)}"
                )
        return self


class ObjectReliefPickPolicy(BaseModel):
    """Partial override on mountain Spec / connection edge (R31)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    mountain: DefaultOnWire[ReliefContextPickPolicy | None] = None
    open_land: DefaultOnWire[ReliefContextPickPolicy | None] = None
    shore: DefaultOnWire[ReliefContextPickPolicy | None] = None
    road_shoulder: DefaultOnWire[ReliefContextPickPolicy | None] = None

    def for_context(self, context: str) -> ReliefContextPickPolicy | None:
        return getattr(self, context)
