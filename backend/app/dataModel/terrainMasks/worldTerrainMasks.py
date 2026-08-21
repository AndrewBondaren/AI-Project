"""``worlds.terrain_masks`` — L0 terrain mask domains (tz_map_light_bake)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, DefaultEnumOnWire
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    WorldConnectionTypeRegistry,
)
from app.dataModel.constrainedField import constrained_field
from app.dataModel.masks.enums.maskDomainId import (
    TERRAIN_MERGE_RANK_HIGH_TO_LOW,
    MaskDomainId,
)
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.mountain.enums import MountainKind, MountainRangeStyle
from app.dataModel.terrainMasks.mountain.specs import (
    MountainDeclareEntry,
    MountainForm,
    MountainFormBySides,
    MountainSideSpec,
    default_sides_for_count,
    form_side_count,
)
from app.dataModel.terrainMasks.hillPolicy import HillPolicy


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
    """Declare + autoresolve mountain massifs — Spec pipeline (not location disk)."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("mountain"))
    threshold: DefaultOnWire[float] = constrained_field(
        default=0.82, greater_equals=0.0, lesser_equals=2.0,
    )
    elevation_bias_weight: DefaultOnWire[float] = constrained_field(default=0.04, greater_equals=0.0)
    relief_weight: DefaultOnWire[float] = constrained_field(default=0.05, greater_equals=0.0)
    ridge_cell_m: DefaultOnWire[int] = Field(default=250, ge=1)
    default_kind: DefaultEnumOnWire[MountainKind] = MountainKind.ROCKY
    default_form: MountainForm = Field(default_factory=MountainFormBySides)
    default_radius_m: DefaultOnWire[int] = Field(default=500, ge=1)
    sides: DefaultOnWire[list[MountainSideSpec]] = Field(default_factory=list)
    default_range_style: DefaultEnumOnWire[MountainRangeStyle] = MountainRangeStyle.BROKEN
    hybrid_smooth_edge_factor: DefaultOnWire[float] = constrained_field(
        default=1.5, greater_equals=0.0,
    )
    range_gap_length_fraction: DefaultOnWire[float] = constrained_field(
        default=0.25, greater_equals=0.0,
    )
    range_gap_height_factor: DefaultOnWire[float] = constrained_field(
        default=1.0, greater_equals=0.0,
    )
    range_gap_spread: DefaultOnWire[float] = constrained_field(
        default=1.4, greater_equals=1.0,
    )
    range_gap_other_radius_factor: DefaultOnWire[float] = constrained_field(
        default=0.25, greater_equals=0.0,
    )
    enable_secondary_ridges: DefaultOnWire[bool] = True

    def resolved_sides(self) -> list[MountainSideSpec]:
        """Assemble Spec.sides — empty → N× MountainSideSpec(); wrong len → raise."""
        n = form_side_count(self.default_form)
        if len(self.sides) == n:
            return list(self.sides)
        if self.sides:
            raise ValueError(
                f"MountainsCategoryPolicy.sides length {len(self.sides)} "
                f"!= form side_count {n}"
            )
        return default_sides_for_count(n)


class ForestsCategoryPolicy(MaskCategoryPolicy):
    """Climate rainfall → forest (cold biomes stay on climate_zone_id, not terrain)."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("forest"))
    forest_min_rainfall: DefaultOnWire[int] = Field(default=45, ge=0)
    hills: DefaultOnWire[HillPolicy] = Field(
        default_factory=HillPolicy.canonical_forest,
    )


class PlainsCategoryPolicy(MaskCategoryPolicy):
    """Background land where higher-rank masks absent."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("plains"))
    hills: DefaultOnWire[HillPolicy] = Field(
        default_factory=HillPolicy.canonical_plains,
    )


class RavinesCategoryPolicy(MaskCategoryPolicy):
    """Local depression → ravine."""

    system_terrain: DefaultOnWire[str] = Field(default_factory=lambda: _terrain_key("ravine"))
    min_drop: DefaultOnWire[int] = Field(default=1, ge=1)
    min_neighbors: DefaultOnWire[int] = Field(default=3, ge=1)
    drop_z: DefaultOnWire[int] = Field(default=1, ge=1)


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
    declared_mountains: DefaultOnWire[list[MountainDeclareEntry]] = Field(default_factory=list)
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

    def system_terrain_for_domain(self, domain: MaskDomainId) -> str | None:
        """Resolve ``system_terrain`` key for a terrain-painting mask domain."""
        accessors: dict[MaskDomainId, str] = {
            MaskDomainId.ROADS: self.default_roads.system_terrain,
            MaskDomainId.RAVINES: self.default_ravines.system_terrain,
            MaskDomainId.MOUNTAINS: self.default_mountains.system_terrain,
            MaskDomainId.FORESTS: self.default_forests.system_terrain,
            MaskDomainId.PLAINS: self.default_plains.system_terrain,
        }
        return accessors.get(domain)

    def merge_rank_order(self) -> tuple[str, ...]:
        """High → low paint priority for ``system_terrain`` (SoT: TERRAIN_MERGE_RANK)."""
        keys: list[str] = []
        for domain in TERRAIN_MERGE_RANK_HIGH_TO_LOW:
            key = self.system_terrain_for_domain(domain)
            if key is not None:
                keys.append(key)
        return tuple(keys)
