"""Landcover generation knobs in fine cells; no application-side defaults."""

from typing import Self

from pydantic import AliasChoices, Field, field_validator, model_serializer

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.spatial.regionShape import EdgeNoise
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey, WorldTerrainRegistry


class LandcoverTerrainPolicy(MaskCategoryPolicy):
    """Optional authored overrides per terrain key; never a separate mask domain."""

    system_terrain: TerrainKey
    min_rainfall: int | None = Field(default=None, ge=0,
        validation_alias=AliasChoices("min_rainfall", "forest_min_rainfall"))
    hills: HillPolicy | None = None

    @property
    def has_authored_hills(self) -> bool:
        return "hills" in self.model_fields_set

    def apply_to(self, entry: TerrainRegistryEntry, *, source: TerrainRegistryEntry | None,
                 registry_hills_authored: bool) -> TerrainRegistryEntry:
        result = entry
        if source is not None and source.system_terrain != entry.system_terrain and not entry.eligibility:
            result = result.with_eligibility(source.eligibility)
        if self.has_authored_hills and not registry_hills_authored:
            result = result.with_hills(self.hills)
        if self.min_rainfall is not None:
            rainfall = WorldTerrainRegistry.minimum_rainfall_rule(self.min_rainfall)
            rules = [rule for rule in result.eligibility if rule.fact != rainfall.fact]
            result = result.with_eligibility([*rules, rainfall])
        return result

    @model_serializer(mode="wrap")
    def serialize_authored_overrides(self, handler):
        result = handler(self)
        for name in ("min_rainfall", "hills"):
            if name not in self.model_fields_set:
                result.pop(name, None)
        return result


class LandcoverClaimNoise(EdgeNoise):
    amplitude: DefaultWhenMissing[int] = Field(default=125, ge=0)
    scale: DefaultWhenMissing[int] = Field(default=250, gt=0)


class LandcoverRegionsCategoryPolicy(MaskCategoryPolicy):
    transition_threshold: DefaultWhenMissing[float] = Field(default=1.0, gt=0, le=1, allow_inf_nan=False)
    seed_spacing: StrictOnWire[int] = Field(gt=0)
    max_radius: DefaultWhenMissing[int] = Field(default=2250, gt=0)
    claim_noise: DefaultWhenMissing[LandcoverClaimNoise] = Field(default_factory=LandcoverClaimNoise)
    fallback_terrain: DefaultWhenMissing[TerrainKey] = Field(
        default_factory=WorldTerrainRegistry.plains_terrain_key)
    terrain_policies: dict[TerrainKey, LandcoverTerrainPolicy] = Field(default_factory=dict)

    @field_validator("claim_noise", mode="before")
    @classmethod
    def claim_noise_wire(cls, value):
        return value.model_dump() if isinstance(value, EdgeNoise) else value

    @classmethod
    def canonical_defaults(cls) -> Self:
        # seed_spacing remains required on explicitly authored policy objects.
        return cls(seed_spacing=1000)

    def terrain_policy(self, key: TerrainKey) -> LandcoverTerrainPolicy:
        return self.terrain_policies.get(key) or LandcoverTerrainPolicy(system_terrain=key)

    def hills_for(self, key: TerrainKey) -> HillPolicy | None:
        override = self.terrain_policies.get(key)
        if override is not None and override.has_authored_hills:
            return override.hills
        entry = WorldTerrainRegistry.canonical_defaults().entry_for(key)
        return entry.hills if entry is not None else None
