"""Explicit immutable evidence sources; no live registry/library or material guesses."""
from typing import Self

from pydantic import BaseModel, ConfigDict, StrictBool, StrictFloat, StrictInt, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.materials.enums.materialCategory import MaterialCategory
from app.dataModel.materials.enums.materialSubstrateKind import MaterialSubstrateKind
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.registryKey import RegistryKey
from app.dataModel.regions.regionState import RegionState
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
from app.dataModel.terrain.worldTerrainCategoryRegistry import WorldTerrainCategoryRegistry
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverClaimNoise, LandcoverTerrainPolicy
from app.dataModel.terrainMasks.mountain.specs import MountainDeclareEntry
from app.dataModel.terrainMasks.regions import LandcoverDeclareEntry
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy


class _SupportRecord(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    @model_validator(mode="after")
    def immutable_sources(self) -> Self:
        validate_immutable(self)
        return self


class MaterialSupportEntry(_SupportRecord, frozen=True):
    key: MaterialKey
    category: MaterialCategory
    substrate: MaterialSubstrateKind | None


class TerrainSupportEntry(_SupportRecord, frozen=True):
    key: TerrainKey
    category: RegistryKey[WorldTerrainCategoryRegistry]
    default_material: MaterialKey | None
    merge_rank: StrictInt
    eligibility: tuple[EligibilityRule, ...]
    hills: HillPolicy | None
    # Authored null overrides inheritance; value alone cannot encode presence.
    hills_authored: StrictBool


class LandcoverSupportPolicy(_SupportRecord, frozen=True):
    enabled: StrictBool
    autoresolve: StrictBool
    transition_threshold: StrictFloat
    seed_spacing: StrictInt
    max_radius: StrictInt
    claim_noise: LandcoverClaimNoise
    fallback_terrain: TerrainKey
    terrain_policies: tuple[LandcoverTerrainPolicy, ...]
    # Consumers use this explicit fact, not decoded model_fields_set.
    terrain_policy_hills_authored: tuple[TerrainKey, ...]

    @model_validator(mode="after")
    def canonical_policy_sources(self) -> Self:
        keys = tuple(p.system_terrain for p in self.terrain_policies)
        authored = self.terrain_policy_hills_authored
        if keys != tuple(sorted(set(keys))) or authored != tuple(sorted(set(authored))) or not set(authored) <= set(keys):
            raise ValueError("landcover policy keys and authored presence require unique sorted matching identities")
        if not 0 < self.transition_threshold <= 1 or self.seed_spacing <= 0 or self.max_radius <= 0:
            raise ValueError("invalid captured landcover generation limits")
        return self


class SurfaceSupportInput(_SupportRecord, frozen=True):
    """Same view for runtime/validation; resolution mode belongs to coating input."""

    seed: StrictInt
    masks_enabled: StrictBool
    grid: SurfaceGridSettings
    topology: WorldTopology
    terrain_entries: tuple[TerrainSupportEntry, ...]
    materials: tuple[MaterialSupportEntry, ...]
    declared_regions: tuple[LandcoverDeclareEntry, ...]
    region_states: tuple[RegionState, ...]
    landcover: LandcoverSupportPolicy
    mountains: tuple[MountainDeclareEntry, ...]
    relief_policies: tuple[tuple[ReliefContext, ReliefContextPickPolicy], ...]
    templates: tuple[tuple[EntityUid, ReliefTemplate], ...]
    refine_policy: ParentLightRefinePolicy

    @model_validator(mode="after")
    def canonical_source_identities(self) -> Self:
        collections = (
            tuple(e.key for e in self.terrain_entries), tuple(e.key for e in self.materials),
            tuple(s.region_uid for s in self.region_states),
            tuple(c.value for c, _ in self.relief_policies), tuple(uid for uid, _ in self.templates),
        )
        if any(keys != tuple(sorted(set(keys))) for keys in collections):
            raise ValueError("support source identities must be unique and sorted")
        if {context for context, _ in self.relief_policies} != set(ReliefContext):
            raise ValueError("support input requires each explicit relief context policy")
        return self
