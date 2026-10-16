"""Defaults for location territory AABB — docs/tz_world_pack_storage.md § Location L2.

Settlement footprint: ``settlement_fine_rect`` is half-open ``[x0,x1)×[y0,y1)``;
``TerritoryVolume`` is inclusive — convert with ``x1_exclusive - 1`` (±1 fine cell on edge vs generator).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy


class TerritoryVolumePolicy(BaseModel):
    SCHEMA_ID: ClassVar[str] = "SCH-TERRITORY-VOLUME-POLICY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    pin_map_z_fallback: int = 0
    pin_z_above: int = 2
    settlement_z_above: int = 32
    min_settlement_separation_xy: int = Field(default=1, ge=0)
    min_settlement_separation_z: int = Field(default=50, ge=0)

    @classmethod
    def canonical_defaults(cls) -> TerritoryVolumePolicy:
        return cls()

    @classmethod
    def pin_half_extent_xy(cls) -> int:
        """Pin box XY half-size — same as ``SceneVolumePolicy.scene_xy_radius`` (WP-13)."""
        return SceneVolumePolicy.canonical_defaults().scene_xy_radius
