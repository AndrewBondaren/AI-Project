"""Scene volume radii — docs/tz_terrain_generation.md § TR-LAZY-LOAD, WP-13."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class SceneVolumePolicy(BaseModel):
    """Gameplay scene load bounds around anchor (meters / fine cells)."""

    SCHEMA_ID: ClassVar[str] = "SCH-SCENE-VOLUME-POLICY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    scene_xy_radius: int = Field(default=20, ge=0)
    scene_z_above: int = Field(default=6, ge=0)
    # WP-13 / WP-PERF-10: background enqueue within this distance of entry (not whole tile).
    background_expand_radius_m: int = Field(default=60, ge=0)

    @classmethod
    def canonical_defaults(cls) -> SceneVolumePolicy:
        return cls()
