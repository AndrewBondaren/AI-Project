"""Scene volume radii — docs/tz_terrain_generation.md § TR-LAZY-LOAD, WP-13."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class SceneVolumePolicy(BaseModel):
    """Gameplay scene load bounds around anchor (meters)."""

    SCHEMA_ID: ClassVar[str] = "SCH-SCENE-VOLUME-POLICY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    scene_xy_radius: int = 5

    @classmethod
    def canonical_defaults(cls) -> SceneVolumePolicy:
        return cls()
