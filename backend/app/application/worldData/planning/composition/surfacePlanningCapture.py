"""Capture resolved source inputs without planning, IO, feature detection or caching."""

from collections.abc import Sequence

from pydantic import BaseModel, TypeAdapter

from app.application.encoding.canonicalCodec import digest
from app.application.jsonValidation.resolve import ResolveContext, resolve_model, report_issues
from app.application.jsonValidation.worldSlices import slice_for_pojo, canonical_registry_wire, _apply_runtime_canonical_merge
from app.application.worldData.generators.climate.anchorCollect import collect_manual_anchors, collect_admin_anchors
from app.application.worldData.generators.climate.climateZone import enum_default_profile, fallback_profile, _profile_from_entry
from app.application.worldData.generators.climate.locations import static_climate_poles
from app.application.worldData.generators.climate.poleResolve import infer_pole_kind
from app.application.worldData.generators.hydrology.load.hydrologyLocations import geographic_locations, geographic_subtype
from app.application.worldData.generators.coordinates.convert import map_cell_fine_span
from app.application.worldData.generators.terrain.mountains.geoAnchors import anchor_mountain_locations
from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
from app.application.worldData.planning.composition.planProviders import SURFACE_MANIFEST
from app.application.worldData.planning.contracts.surfacePlanningView import (
    SurfacePlanningView, ReadySurfacePlanningView, NoExtentSurfacePlanningView,
)
from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
from app.dataModel.climate.enums.climateZone import ClimateZoneProfileData
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.planning.climatePlan import ResolvedClimateProfile
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput, ManualPoleInput
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput, ClimateFeaturePolicy
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.enums.planning.hydrologyScope import HYDROLOGY_BOOTSTRAP_SCOPES
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput, HydrologyFinalInput, HydrologyAnchorInput
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.identity.uid import EntityUid
from app.dataModel.registryKey import RegistryKey
from app.dataModel.materials.enums.materialCategory import MaterialCategory
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import StateViewRevision
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ, FineXY
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput, WaterAnchorInput
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import (
    ReliefPlanInput, RiverReliefInput, MountainAnchorInput, TerrainMergeEntry,
)
from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.worldPack.wire.worldMapCellsPerTile import resolve_world_map_side
from app.db.models.world import World
from app.db.models.namedLocation import NamedLocation
from app.ids import seed_int
from app.ids.waterSystemIdentity import initial_water_change_uid


def _read[M: BaseModel](world: World, model: type[M], ctx: ResolveContext) -> M:
    """Use the existing slice catalog/normalization with this request's report policy."""
    source = slice_for_pojo(model)
    if source is None:
        raise ValueError("capture source has no registered WorldSlice")
    if source.wire_from_mapping is not None:
        raw = source.wire_from_mapping(world)
    else:
        raw = getattr(world, source.world_keys[0])
        if source.wire_adapter is not None:
            raw = source.wire_adapter(raw)
        if source.wire_kind == "registry_list":
            raw = canonical_registry_wire(source, raw)
        if raw is None or (source.wire_kind == "registry_list" and raw == []):
            if source.empty_factory is None:
                raise ValueError("missing capture source without declared defaults")
            return model.model_validate(source.empty_factory())
    active_ctx = ctx if source.wire_from_mapping is not None else ctx.child(source.world_keys[0])
    resolved = resolve_model(model, raw, ctx=active_ctx)
    return model.model_validate(_apply_runtime_canonical_merge(source, resolved))


def _position(location: NamedLocation) -> FineXY | None:
    if location.map_x is None or location.map_y is None:
        return None
    return FineX(location.map_x), FineY(location.map_y)


def _revision(world_uid: EntityUid, inputs: tuple[BaseModel, ...]) -> StateViewRevision:
    projection = tuple(tuple((name, getattr(value, name)) for name in type(value).model_fields
        if not (isinstance(value, (WaterPlacementInput, HydrologyPlanInput)) and name == "resolution_mode"))
        for value in inputs)
    return StateViewRevision(digest((world_uid, projection), SURFACE_MANIFEST))


class SurfacePlanningCapture:
    def capture(self, world: World, locations: Sequence[NamedLocation], *, mode: ResolutionMode,
                mountain_templates: tuple[MountainTemplateInput, ...],
                resolve_ctx: ResolveContext) -> SurfacePlanningView:
        if resolve_ctx.validate_only != (mode is ResolutionMode.VALIDATE_ONLY):
            raise ValueError("capture mode must match the request ResolveContext")
        start = len(resolve_ctx.errors)
        rows = list(locations)
        world_uid = TypeAdapter[EntityUid](EntityUid).validate_python(world.world_uid)
        seed = seed_int(world)
        scalars = _read(world, WorldClimateScalars, resolve_ctx)
        climate_registry = _read(world, WorldClimateZoneRegistry, resolve_ctx)
        span = map_cell_fine_span(world)
        bbox = grid_bbox_from_locations(world, rows)
        peak_min, peak_max = WorldClimateScalars.resolve_peak_bounds(
            scalars.climate_temperature_peak_min, scalars.climate_temperature_peak_max)
        preset = ClimatePolePreset.from_wire(scalars.climate_pole_preset)
        manual = tuple(ManualPoleInput(location_uid=loc.location_uid, position=pos,
            kind=PoleKind(infer_pole_kind(loc)), zone=RegistryKey[WorldClimateZoneRegistry](loc.system_climate_zone) if loc.system_climate_zone else None)
            for loc in static_climate_poles(rows) if (pos := _position(loc)) is not None)
        keys = {scalars.default_climate_zone, *(point.zone for point in manual if point.zone is not None),
            *(spec.system_climate_zone for spec in preset.pole_specs())}
        profiles: list[ResolvedClimateProfile] = []
        for key in sorted(keys):
            fallback = enum_default_profile(key)
            entry = climate_registry.entry_for(key)
            if entry is None and fallback is None:
                report_issues(resolve_ctx, (FieldPathError(("climate_zone_registry", key),
                    "unknown climate profile; using canonical fallback", code="unknown_climate"),))
            base = fallback if fallback is not None else fallback_profile()
            profile = base if entry is None else _profile_from_entry(entry, fallback=base)
            profiles.append(ResolvedClimateProfile(key=RegistryKey[WorldClimateZoneRegistry](key), values=ClimateZoneProfileData(
                base_temperature=profile.base_temperature, typical_elevation_z=profile.typical_elevation_z,
                base_rainfall=profile.base_rainfall, temperature_variance=profile.temperature_variance,
                rainfall_variance=profile.rainfall_variance)))
        climate = ClimateBaseInput(seed=seed, bbox=bbox, fine_span=span,
            mode=ClimatePoleMode.from_wire(scalars.climate_pole_mode), preset=preset,
            peak_min=peak_min, peak_max=peak_max, default_zone=RegistryKey[WorldClimateZoneRegistry](scalars.default_climate_zone),
            manual_poles=manual, profiles=tuple(profiles), blend=CLIMATE_POLE_BLEND)
        local = ClimateLocalInput(manual=tuple(collect_manual_anchors(rows, span)),
            admin=tuple(collect_admin_anchors(rows, span)), feature_policy=ClimateFeaturePolicy(
                synthetic_surface_terrain=WorldTerrainRegistry.canonical_defaults().root[0].system_terrain,
                water_feature_terrain=RegistryKey[WorldTerrainRegistry](
                    WorldTerrainRegistry.require_engine_terrain_key("liquid_body"))))
        if bbox is None:
            return NoExtentSurfacePlanningView(world_uid=world_uid, revision=_revision(world_uid, (climate, local)),
                capture_diagnostics=self._diagnostics(resolve_ctx, start))
        terrain_scalars = _read(world, WorldTerrainScalars, resolve_ctx)
        z_min = FineZ(WorldTerrainScalars.resolved_z_min(terrain_scalars.z_min))
        z_max = FineZ(WorldTerrainScalars.resolved_z_max(terrain_scalars.z_max))
        grid = SurfaceGridSettings(fine_span=span, light_side=resolve_world_map_side(world.world_map_cells_per_tile))
        topology = WorldTopology(mode=terrain_scalars.world_topology_mode, bounds=WorldBounds(
            x_min=bbox.x_min, x_max=bbox.x_max, y_min=bbox.y_min, y_max=bbox.y_max))
        terrain = TerrainBaseInput(seed=seed, bbox=bbox, z_min=z_min, z_max=z_max, grid=grid)
        hydro = _read(world, WorldHydrology, resolve_ctx)
        masks = _read(world, WorldTerrainMasks, resolve_ctx)
        materials = _read(world, WorldMaterialRegistry, resolve_ctx)
        liquid_keys = frozenset(entry.system_material for entry in materials.root
            if entry.material_category is MaterialCategory.LIQUID)
        geographic_uids = {loc.location_uid for loc in geographic_locations(rows)}
        anchors = tuple(HydrologyAnchorInput(location_uid=loc.location_uid, position=_position(loc),
            z=FineZ(loc.map_z) if loc.map_z is not None else None,
            subtype=geographic_subtype(loc) if loc.location_uid in geographic_uids else None)
            for loc in sorted(rows, key=lambda loc: loc.location_uid))
        water = WaterPlacementInput(enabled=hydro.enabled, resolution_mode=mode,
            default_water_level=FineZ(hydro.default_water_level), seas=hydro.default_seas, lakes=hydro.default_lakes,
            basins=tuple(hydro.declared_basins), coastlines=tuple(hydro.declared_coastlines),
            declared_lakes=tuple(hydro.declared_lakes), anchors=tuple(WaterAnchorInput(
                source_uid=anchor.location_uid, position=anchor.position, subtype=anchor.subtype)
                for anchor in anchors if anchor.position is not None
                and anchor.location_uid in geographic_uids), topology=topology, grid=grid,
            z_min=z_min, z_max=z_max, liquid_keys=liquid_keys)
        relief = ReliefPlanInput(seed=seed, masks_enabled=masks.enabled, mountains=masks.default_mountains,
            ravines=masks.default_ravines, declared_mountains=tuple(masks.declared_mountains),
            anchors=tuple(MountainAnchorInput(location_uid=loc.location_uid, position=pos)
                for loc in sorted(anchor_mountain_locations(rows), key=lambda loc: loc.location_uid)
                if (pos := _position(loc)) is not None), grid=grid, z_min=z_min, z_max=z_max,
            mountain_templates=mountain_templates, mountain_pick=_read(world, WorldReliefPickPolicy, resolve_ctx).mountain,
            terrain_merge=tuple(TerrainMergeEntry(key=entry.system_terrain, merge_rank=entry.merge_rank)
                for entry in sorted(_read(world, WorldTerrainRegistry, resolve_ctx).root, key=lambda e: e.system_terrain)))
        routes = HydrologyPlanInput(enabled=hydro.enabled, seed=seed, resolution_mode=mode,
            scopes=HYDROLOGY_BOOTSTRAP_SCOPES, default_water_level=FineZ(hydro.default_water_level),
            seas=hydro.default_seas, lakes=hydro.default_lakes, rivers=hydro.default_rivers,
            declared_rivers=tuple(hydro.declared_rivers), coastlines=tuple(hydro.declared_coastlines),
            declared_lakes=tuple(hydro.declared_lakes), anchors=anchors, topology=topology, grid=grid,
            z_min=z_min, z_max=z_max, liquid_keys=liquid_keys,
            change_uid=initial_water_change_uid(world_uid))
        river = RiverReliefInput(z_min=z_min, z_max=z_max, grid=grid, topology=topology,
            channel_depths=tuple((kind, hydro.default_rivers.channel_depth_for(kind)) for kind in sorted(
                (HydrologyConnectionType.RIVER, HydrologyConnectionType.MOUNTAIN_RIVER), key=lambda kind: kind.value)))
        final = HydrologyFinalInput(enabled=hydro.enabled, grid=grid, topology=topology)
        return ReadySurfacePlanningView(world_uid=world_uid,
            revision=_revision(world_uid, (climate, terrain, water, relief, routes, river, final, local)),
            climate_base=climate, terrain_base=terrain, water_placement=water, relief=relief,
            hydrology=routes, river_relief=river, hydrology_final=final, climate_local=local,
            capture_diagnostics=self._diagnostics(resolve_ctx, start))

    @staticmethod
    def _diagnostics(ctx: ResolveContext, start: int) -> tuple[PlanDiagnostic, ...]:
        return tuple(PlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.FALLBACK)
            for issue in dict.fromkeys(ctx.errors[start:]))


class SurfacePlanningStale(ValueError):
    def __init__(self, expected: StateViewRevision, actual: StateViewRevision) -> None:
        self.expected, self.actual = expected, actual
        super().__init__("surface source changed before publication")


def require_current_source(captured: SurfacePlanningView, current: SurfacePlanningView) -> None:
    if captured.world_uid != current.world_uid or captured.revision != current.revision:
        raise SurfacePlanningStale(captured.revision, current.revision)
