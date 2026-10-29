"""Captured registry/region projection; source selection uses the landcover kernels."""
from dataclasses import dataclass, replace
from functools import cmp_to_key, partial

from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
from app.application.worldData.generators.terrain.landcover.autoresolve.claim import autoresolve_regions
from app.application.worldData.generators.terrain.landcover.types import ResolvedRegion, RegionSource, StateSnapshotEntry
from app.application.worldData.regions.inputs.landcoverInputs import LandcoverObservations
from app.application.worldData.regions.coverageBackground import coverage_registry, surface_coverage
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.application.worldData.masks.regionRasterContext import RegionRasterContext
from app.application.worldData.masks.regionRasterizer import rasterize_fine, rasterize_claim_fine
from app.application.worldData.masks.regionPrecedence import RegionCandidate, compare_region_candidates
from app.application.worldData.masks.terrainMerge import terrain_merge_rank, may_paint_terrain
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.spatial.grid.coordinateTypes import FineXY, GridX, GridY
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.spatial.regionShape import AnchorRadiusShape
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey, WorldTerrainRegistry
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy


@dataclass(frozen=True)
class CapturedRegionWorld:
    world_uid: str


class SupportSources:
    """Request-owned scratch state; never stored in a plan payload."""

    def __init__(self, world_uid: str, inputs: SurfaceSupportInput, climate_base: ClimateBasePlan,
                 climate_local: ClimateLocalPlan, terrain: TerrainPlan, hydrology: HydrologyPlan):
        self.world = CapturedRegionWorld(world_uid)
        self.inputs = inputs
        self.registry = WorldTerrainRegistry([TerrainRegistryEntry(
            system_terrain=e.key, terrain_category=e.category, default_material=e.default_material,
            merge_rank=e.merge_rank, eligibility=list(e.eligibility), hills=e.hills) for e in inputs.terrain_entries])
        landcover = inputs.landcover
        self.policy = LandcoverRegionsCategoryPolicy(enabled=landcover.enabled, autoresolve=landcover.autoresolve,
            transition_threshold=landcover.transition_threshold, seed_spacing=landcover.seed_spacing,
            max_radius=landcover.max_radius, claim_noise=landcover.claim_noise,
            fallback_terrain=landcover.fallback_terrain, terrain_policies={p.system_terrain: p for p in landcover.terrain_policies})
        # Preserve authored presence through canonical decode; do not consult model_fields_set.
        entries = {e.system_terrain: e for e in self.registry.root}
        for override in landcover.terrain_policies:
            entry = entries.get(override.system_terrain)
            if entry is None:
                continue
            captured = next(e for e in inputs.terrain_entries if e.key == override.system_terrain)
            fields = {"system_terrain", "enabled", "autoresolve", "min_rainfall"}
            if override.system_terrain in landcover.terrain_policy_hills_authored:
                fields.add("hills")
            restored = type(override).model_construct(_fields_set=fields, **{
                name: getattr(override, name) for name in type(override).model_fields})
            entries[override.system_terrain] = restored.apply_to(entry, source=entry,
                                                               registry_hills_authored=captured.hills_authored)
        self.registry = WorldTerrainRegistry(list(entries.values()))
        profiles = {p.key: ClimateZoneProfile.from_data(p.key, p.values) for p in climate_base.profiles}
        self.climate = ClimateWorkingFields.from_plans(climate_base, climate_local, profiles.__getitem__)
        observations = LandcoverObservations.from_views(inputs.topology, inputs.grid, self.climate,
            TerrainWorkingFields.from_plan(terrain), HydrologyWorkingFields.from_plan(hydrology, inputs.grid))
        self.landcover_inputs = observations.inputs({s.region_uid: StateSnapshotEntry(s.current_type, s.tombstone,
            s.spec_fingerprint) for s in inputs.region_states})
        self.scale = LightGridScale.from_tile(inputs.grid.fine_span, inputs.grid.light_side)
        self.regions: list[ResolvedRegion] = []
        self.claim_index = None
        self.missing_anchor = False
        self._tiles: dict[tuple[int, int], dict[tuple[int, int], TerrainKey]] = {}
        if inputs.masks_enabled and self.policy.enabled:
            if self.policy.autoresolve:
                self.regions, self.claim_index = autoresolve_regions(world_uid, world_uid, inputs.grid.fine_span,
                    self.landcover_inputs, self.policy, coverage_registry(self.registry, self.policy, autoresolve=True))
            for spec in inputs.declared_regions:
                uid = declared_region_identity(world_uid, spec).region_uid
                self.regions.append(ResolvedRegion(world_uid, uid, spec, RegistryKey[WorldTerrainRegistry](spec.entry_type),
                    RegionSource.DECLARED, inputs.topology, entry_type=RegistryKey[WorldTerrainRegistry](spec.entry_type)))
            states = {s.region_uid: s for s in inputs.region_states}
            resolved = []
            for region in self.regions:
                state = states.get(region.region_uid)
                if state is not None and state.tombstone:
                    continue
                region = replace(region, current_type=state.current_type) if state is not None else region
                if isinstance(region.spec.shape, AnchorRadiusShape):
                    self.missing_anchor = True
                    continue
                if self.registry.entry_for(region.current_type) is None:
                    raise ValueError("captured region terrain is missing from support registry")
                if not self.policy.terrain_policy(region.current_type).enabled:
                    continue
                resolved.append(region)
            self.regions = resolved

    def terrain_at(self, cell: FineXY) -> TerrainKey | None:
        if not self.inputs.masks_enabled or not self.policy.enabled or self.missing_anchor:
            return None
        span = self.inputs.grid.fine_span
        tile = cell[0] // span, cell[1] // span
        if tile not in self._tiles:
            gx, gy = tile
            sample = self.climate.sample_pole(GridX(gx), GridY(gy))
            anchor = self.climate.local_field.nearest(gx, gy)
            profile = self.climate.profile_for_key(anchor.system_climate_zone if anchor is not None else sample.system_climate_zone)
            background = surface_coverage(registry=self.registry, policy=self.policy, profile=profile)
            painted = {(x, y): RegistryKey[WorldTerrainRegistry](background) for y in range(gy * span, (gy + 1) * span)
                       for x in range(gx * span, (gx + 1) * span)} if background is not None else {}
            candidates = [RegionCandidate(r.current_type, r.spec, r.region_uid, r.claim_area,
                declared=r.source is not RegionSource.AUTORESOLVE) for r in self.regions]
            rank = partial(terrain_merge_rank, registry=self.registry)
            ordered = sorted(zip(candidates, self.regions), key=cmp_to_key(
                lambda a, b: compare_region_candidates(a[0], b[0], merge_rank=rank)))
            winners: set[tuple[int, int]] = set()
            bbox = (gx * span, gy * span, (gx + 1) * span - 1, (gy + 1) * span - 1)
            for candidate, region in ordered:
                context = RegionRasterContext(region.region_uid, region.spec, self.scale, self.inputs.topology)
                coords = (rasterize_claim_fine(self.claim_index, self.world, context, scope=bbox)
                          if region.claim is not None and self.claim_index is not None
                          else rasterize_fine(region.spec.shape, self.world, context))
                for xy in coords:
                    if xy in winners or not (bbox[0] <= xy[0] <= bbox[2] and bbox[1] <= xy[1] <= bbox[3]):
                        continue
                    winners.add(xy)
                    if painted.get(xy) == background or may_paint_terrain(painted.get(xy), candidate.current_type, self.registry):
                        painted[xy] = candidate.current_type
            self._tiles[tile] = painted
        return self._tiles[tile].get(cell)
