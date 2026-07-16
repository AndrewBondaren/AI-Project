"""``worlds.terrain_masks`` — L0 terrain mask domains (tz_map_light_bake)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.constrainedField import constrained_field
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


def _terrain_key(system_terrain: str) -> str:
    entry = WorldTerrainRegistry.canonical_defaults().entry_for(system_terrain)
    if entry is None:
        raise RuntimeError(f"WorldTerrainRegistry.canonical_defaults missing {system_terrain!r}")
    return entry.system_terrain


def _road_connection_types() -> tuple[str, ...]:
    reg = WorldConnectionTypeRegistry.canonical_defaults()
    keys = ("trail", "dirt_road", "road", "highway", "bridge")
    return tuple(
        e.system_connection_type
        for key in keys
        if (e := reg.entry_for(key)) is not None
    )


class MountainsCategoryPolicy(MaskCategoryPolicy):
    """Declare + autoresolve mountain massifs."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("mountain"))
    # Autoresolve: score = ridge_noise + elev_bias + relief_term; paint if >= threshold.
    threshold: DefaultOnWire[float] = constrained_field(
        default=0.82, greater_equals=0.0, lesser_equals=2.0,
    )
    elevation_bias_weight: DefaultOnWire[float] = constrained_field(default=0.04, greater_equals=0.0)
    relief_weight: DefaultOnWire[float] = constrained_field(default=0.05, greater_equals=0.0)
    # Light-cell disk radius around geographic.mountain / peak anchors.
    declare_radius_light: DefaultOnWire[int] = Field(default=3, ge=0)
    # Quantize meters for ridge noise (must be ≪ tile_m so L0 sees variation).
    ridge_cell_m: DefaultOnWire[int] = Field(default=250, ge=1)


class ForestsCategoryPolicy(MaskCategoryPolicy):
    """Climate rainfall → forest."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("forest"))
    forest_min_rainfall: DefaultOnWire[int] = Field(default=45, ge=0)
    tundra_system_terrain: DefaultOnWire[str] = "tundra"
    tundra_max_base_temperature: DefaultOnWire[int] = 0


class PlainsCategoryPolicy(MaskCategoryPolicy):
    """Background land where higher-rank masks absent."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("plains"))


class RavinesCategoryPolicy(MaskCategoryPolicy):
    """Local depression → ravine."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("ravine"))
    min_drop: DefaultOnWire[int] = Field(default=1, ge=1)
    min_neighbors: DefaultOnWire[int] = Field(default=3, ge=1)


class RoadsCategoryPolicy(MaskCategoryPolicy):
    """Structure edges → road terrain (no edges ⇒ empty mask)."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("road"))
    connection_types: DefaultOnWire[tuple[str, ...]] = Field(default_factory=_road_connection_types)
    graph_levels: DefaultOnWire[tuple[str, ...]] = ("world",)
    dilate_radius_light: DefaultOnWire[int] = Field(default=0, ge=0)


class WorldTerrainMasks(BaseModel):
    """Root POJO for ``worlds.terrain_masks`` JSON object."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-TERRAIN-MASKS"

    model_config = ConfigDict(extra="ignore", frozen=True)

    enabled: DefaultOnWire[bool] = True
    default_mountains: DefaultOnWire[MountainsCategoryPolicy] = Field(
        default_factory=MountainsCategoryPolicy,
    )
    default_forests: DefaultOnWire[ForestsCategoryPolicy] = Field(
        default_factory=ForestsCategoryPolicy,
    )
    default_plains: DefaultOnWire[PlainsCategoryPolicy] = Field(
        default_factory=PlainsCategoryPolicy,
    )
    default_ravines: DefaultOnWire[RavinesCategoryPolicy] = Field(
        default_factory=RavinesCategoryPolicy,
    )
    default_roads: DefaultOnWire[RoadsCategoryPolicy] = Field(
        default_factory=RoadsCategoryPolicy,
    )

    @classmethod
    def canonical_defaults(cls) -> WorldTerrainMasks:
        return cls()

    @classmethod
    def canonical_empty(cls) -> WorldTerrainMasks:
        """Normalize missing/`{}` → full defaults (same as hydrology)."""
        return cls()

    def category_enabled(self, category: MaskCategoryPolicy) -> bool:
        return bool(self.enabled) and bool(category.enabled)

    def merge_rank_order(self) -> tuple[str, ...]:
        """High → low paint priority for ``system_terrain``."""
        return (
            self.default_roads.system_terrain,
            self.default_ravines.system_terrain,
            self.default_mountains.system_terrain,
            self.default_forests.system_terrain,
            self.default_plains.system_terrain,
        )
