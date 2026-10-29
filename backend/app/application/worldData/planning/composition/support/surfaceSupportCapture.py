"""Project a coherent caller view; library IO and domain decisions stay with owners."""
from app.application.templateLibrary.templateContracts import ReliefTemplateSnapshot
from app.dataModel.identity.uid import EntityUid
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.regions.regionState import RegionState
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import (
    LandcoverSupportPolicy, MaterialSupportEntry, SurfaceSupportInput, TerrainSupportEntry,
)
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy
from app.dataModel.terrain.worldTerrainCategoryRegistry import WorldTerrainCategoryRegistry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy


class SurfaceSupportCapture:
    """Membership-scoped full bodies and immutable projections, without generator calls."""

    def capture(self, world_uid: EntityUid, *, seed: int, grid: SurfaceGridSettings,
                topology: WorldTopology, terrain: WorldTerrainRegistry, materials: WorldMaterialRegistry,
                masks: WorldTerrainMasks, region_states: tuple[RegionState, ...],
                relief_policy: WorldReliefPickPolicy, templates: ReliefTemplateSnapshot,
                refine_policy: ParentLightRefinePolicy) -> SurfaceSupportInput:
        if not isinstance(templates, ReliefTemplateSnapshot) or templates.world_uid != world_uid:
            raise ValueError("surface support requires membership from the same captured world")
        if not isinstance(terrain, WorldTerrainRegistry) or not isinstance(materials, WorldMaterialRegistry):
            raise TypeError("support capture requires typed terrain and material registries")
        if not isinstance(masks, WorldTerrainMasks) or not isinstance(relief_policy, WorldReliefPickPolicy):
            raise TypeError("support capture requires typed masks and relief policy")
        if not isinstance(grid, SurfaceGridSettings) or not isinstance(topology, WorldTopology):
            raise TypeError("support capture requires the captured typed grid and topology")
        if not isinstance(refine_policy, ParentLightRefinePolicy) or not isinstance(region_states, tuple) or any(
                not isinstance(state, RegionState) for state in region_states):
            raise TypeError("support capture requires a typed refine policy and tuple of region states")
        policy = masks.default_landcover
        if any(key != value.system_terrain for key, value in policy.terrain_policies.items()):
            raise ValueError("landcover policy dictionary key must equal system_terrain")
        landcover = LandcoverSupportPolicy(enabled=policy.enabled, autoresolve=policy.autoresolve,
            transition_threshold=policy.transition_threshold, seed_spacing=policy.seed_spacing,
            max_radius=policy.max_radius, claim_noise=policy.claim_noise, fallback_terrain=policy.fallback_terrain,
            terrain_policies=tuple(value for _, value in sorted(policy.terrain_policies.items())),
            terrain_policy_hills_authored=tuple(sorted(key for key, value in policy.terrain_policies.items() if value.has_authored_hills)))
        return SurfaceSupportInput(seed=seed, masks_enabled=masks.enabled, grid=grid, topology=topology,
            terrain_entries=tuple(TerrainSupportEntry(key=row.system_terrain,
                category=RegistryKey[WorldTerrainCategoryRegistry](row.terrain_category),
                default_material=RegistryKey[WorldMaterialRegistry](row.default_material) if row.default_material is not None else None,
                merge_rank=row.merge_rank, eligibility=tuple(row.eligibility), hills=row.hills,
                hills_authored=row.has_authored_hills) for row in sorted(terrain.root,key=lambda r:r.system_terrain)),
            materials=tuple(MaterialSupportEntry(key=row.system_material,category=row.material_category,
                substrate=row.substrate_kind) for row in sorted(materials.root,key=lambda r:r.system_material)),
            declared_regions=tuple(masks.declared_regions), region_states=tuple(sorted(region_states,key=lambda s:s.region_uid)),
            landcover=landcover, mountains=tuple(masks.declared_mountains),
            relief_policies=tuple((context,relief_policy.for_context(context.value)) for context in sorted(ReliefContext,key=lambda c:c.value)),
            templates=tuple((uid,entry.body) for uid,entry in sorted(templates.templates.items())),refine_policy=refine_policy)
