"""Capture resolved source inputs without planning, IO, feature detection or caching."""

from collections.abc import Sequence

from pydantic import BaseModel, TypeAdapter

from app.application.encoding.canonicalCodec import digest
from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.worldSlices import resolve_world_slice
from app.application.worldData.generators.climate.anchorCollect import collect_manual_anchors, collect_admin_anchors
from app.application.worldData.generators.climate.registry import resolve_base_profiles
from app.application.worldData.generators.climate.locations import static_climate_poles
from app.application.worldData.generators.climate.poleResolve import infer_pole_kind
from app.application.worldData.generators.hydrology.load.hydrologyLocations import geographic_locations, geographic_subtype
from app.application.worldData.generators.coordinates.convert import map_cell_fine_span
from app.application.worldData.generators.terrain.mountains.geoAnchors import anchor_mountain_locations
from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.application.worldData.planning.contracts.surfacePlanningView import (
    SurfacePlanningView, ReadySurfacePlanningView, NoExtentSurfacePlanningView,
)
from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
from app.dataModel.climate.enums.poleKind import PoleKind
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
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry, MaterialKey
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.planning.identity.sourceFieldRole import SourceFieldRole
from app.dataModel.planning.identity.planKey import StateViewRevision
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ, FineXY
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput, WaterAnchorInput
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import (
    ReliefPlanInput, RiverReliefInput, MountainAnchorInput, TerrainMergeEntry,
)
from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.worldPack.wire.worldMapCellsPerTile import resolve_world_map_side
from app.db.models.world import World
from app.db.models.namedLocation import NamedLocation
from app.ids import seed_int
from app.ids.waterSystemIdentity import initial_water_change_uid


def _position(location: NamedLocation) -> FineXY | None:
    if location.map_x is None or location.map_y is None:
        return None
    return FineX(location.map_x), FineY(location.map_y)


def _revision(world_uid: EntityUid, inputs: tuple[BaseModel, ...]) -> StateViewRevision:
    projection = tuple(tuple((name, getattr(value, name)) for name, field in type(value).model_fields.items()
        if SourceFieldRole.EXECUTION_POLICY not in field.metadata)
        for value in inputs)
    return StateViewRevision(digest((world_uid, projection), SURFACE_MANIFEST))


class SurfacePlanningCapture:
    def capture(self, world: World, locations: Sequence[NamedLocation], *, mode: ResolutionMode,
                mountain_templates: tuple[MountainTemplateInput, ...],
                resolve_ctx: ResolveContext) -> SurfacePlanningView:
        if resolve_ctx.validate_only != (mode is ResolutionMode.VALIDATE_ONLY):
            raise ValueError("capture mode must match the request ResolveContext")
        rows = list(locations)
        world_uid = TypeAdapter[EntityUid](EntityUid).validate_python(world.world_uid)
        seed, span = seed_int(world), map_cell_fine_span(world)
        bbox = grid_bbox_from_locations(world, rows)
        climate, diagnostics = self._climate(world, rows, seed, span, bbox, resolve_ctx)
        local = self._local(rows, span)
        if bbox is None:
            return NoExtentSurfacePlanningView(world_uid=world_uid, revision=_revision(world_uid, (climate, local)),
                capture_diagnostics=diagnostics)
        scalars = resolve_world_slice(world, WorldTerrainScalars, ctx=resolve_ctx)
        grid = SurfaceGridSettings(fine_span=span, light_side=resolve_world_map_side(world.world_map_cells_per_tile))
        topology = WorldTopology(mode=scalars.world_topology_mode, bounds=WorldBounds(
            x_min=bbox.x_min, x_max=bbox.x_max, y_min=bbox.y_min, y_max=bbox.y_max))
        terrain = TerrainBaseInput(seed=seed, bbox=bbox, grid=grid,
            z_min=FineZ(WorldTerrainScalars.resolved_z_min(scalars.z_min)),
            z_max=FineZ(WorldTerrainScalars.resolved_z_max(scalars.z_max)))
        hydro = resolve_world_slice(world, WorldHydrology, ctx=resolve_ctx)
        materials = resolve_world_slice(world, WorldMaterialRegistry, ctx=resolve_ctx)
        liquid_keys = frozenset(entry.system_material for entry in materials.root
            if entry.material_category is MaterialCategory.LIQUID)
        geographic_uids = frozenset(loc.location_uid for loc in geographic_locations(rows))
        anchors = self._anchors(rows, geographic_uids)
        water = self._water(hydro, anchors, geographic_uids, terrain, topology, mode, liquid_keys)
        relief = self._relief(world, rows, terrain, mountain_templates, resolve_ctx)
        routes = self._routes(world_uid, hydro, anchors, terrain, topology, mode, liquid_keys)
        river = self._river_relief(routes)
        final = HydrologyFinalInput(enabled=hydro.enabled, grid=grid, topology=topology)
        return ReadySurfacePlanningView(world_uid=world_uid,
            revision=_revision(world_uid, (climate, terrain, water, relief, routes, river, final, local)),
            climate_base=climate, terrain_base=terrain, water_placement=water, relief=relief,
            hydrology=routes, river_relief=river, hydrology_final=final, climate_local=local,
            capture_diagnostics=diagnostics)

    @staticmethod
    def _climate(world: World, rows: list[NamedLocation], seed: int, span: int, bbox: GridBBox | None,
                 resolve_ctx: ResolveContext) -> tuple[ClimateBaseInput, tuple[PlanDiagnostic, ...]]:
        scalars = resolve_world_slice(world, WorldClimateScalars, ctx=resolve_ctx)
        climate_registry = resolve_world_slice(world, WorldClimateZoneRegistry, ctx=resolve_ctx)
        peak_min, peak_max = WorldClimateScalars.resolve_peak_bounds(
            scalars.climate_temperature_peak_min, scalars.climate_temperature_peak_max)
        preset = ClimatePolePreset.from_wire(scalars.climate_pole_preset)
        manual = tuple(ManualPoleInput(location_uid=loc.location_uid, position=pos,
            kind=PoleKind(infer_pole_kind(loc)), zone=RegistryKey[WorldClimateZoneRegistry](loc.system_climate_zone) if loc.system_climate_zone else None)
            for loc in static_climate_poles(rows) if (pos := _position(loc)) is not None)
        profiles, diagnostics = resolve_base_profiles(
            RegistryKey[WorldClimateZoneRegistry](scalars.default_climate_zone), manual, preset,
            climate_registry, resolve_ctx)
        climate = ClimateBaseInput(seed=seed, bbox=bbox, fine_span=span,
            mode=ClimatePoleMode.from_wire(scalars.climate_pole_mode), preset=preset,
            peak_min=peak_min, peak_max=peak_max, default_zone=RegistryKey[WorldClimateZoneRegistry](scalars.default_climate_zone),
            manual_poles=manual, profiles=profiles, blend=CLIMATE_POLE_BLEND)
        return climate, diagnostics

    @staticmethod
    def _local(rows: list[NamedLocation], span: int) -> ClimateLocalInput:
        return ClimateLocalInput(manual=tuple(collect_manual_anchors(rows, span)),
            admin=tuple(collect_admin_anchors(rows, span)), feature_policy=ClimateFeaturePolicy(
                synthetic_surface_terrain=WorldTerrainRegistry.canonical_defaults().root[0].system_terrain,
                water_feature_terrain=RegistryKey[WorldTerrainRegistry](
                    WorldTerrainRegistry.require_engine_terrain_key("liquid_body"))))

    @staticmethod
    def _anchors(rows: list[NamedLocation], geographic_uids: frozenset[str]) -> tuple[HydrologyAnchorInput, ...]:
        return tuple(HydrologyAnchorInput(location_uid=loc.location_uid, position=_position(loc),
            z=FineZ(loc.map_z) if loc.map_z is not None else None,
            subtype=geographic_subtype(loc) if loc.location_uid in geographic_uids else None)
            for loc in sorted(rows, key=lambda loc: loc.location_uid))

    @staticmethod
    def _water(hydro: WorldHydrology, anchors: tuple[HydrologyAnchorInput, ...], geographic_uids: frozenset[str],
               terrain: TerrainBaseInput, topology: WorldTopology, mode: ResolutionMode,
               liquid_keys: frozenset[MaterialKey]) -> WaterPlacementInput:
        water = WaterPlacementInput(enabled=hydro.enabled, resolution_mode=mode,
            default_water_level=FineZ(hydro.default_water_level), seas=hydro.default_seas, lakes=hydro.default_lakes,
            basins=tuple(hydro.declared_basins), coastlines=tuple(hydro.declared_coastlines),
            declared_lakes=tuple(hydro.declared_lakes), anchors=tuple(WaterAnchorInput(
                source_uid=anchor.location_uid, position=anchor.position, subtype=anchor.subtype)
                for anchor in anchors if anchor.position is not None
                and anchor.location_uid in geographic_uids), topology=topology, grid=terrain.grid,
            z_min=terrain.z_min, z_max=terrain.z_max, liquid_keys=liquid_keys)
        return water

    @staticmethod
    def _relief(world: World, rows: list[NamedLocation], terrain: TerrainBaseInput,
                mountain_templates: tuple[MountainTemplateInput, ...], resolve_ctx: ResolveContext) -> ReliefPlanInput:
        masks = resolve_world_slice(world, WorldTerrainMasks, ctx=resolve_ctx)
        relief = ReliefPlanInput(seed=terrain.seed, masks_enabled=masks.enabled, mountains=masks.default_mountains,
            ravines=masks.default_ravines, declared_mountains=tuple(masks.declared_mountains),
            anchors=tuple(MountainAnchorInput(location_uid=loc.location_uid, position=pos)
                for loc in sorted(anchor_mountain_locations(rows), key=lambda loc: loc.location_uid)
                if (pos := _position(loc)) is not None), grid=terrain.grid, z_min=terrain.z_min, z_max=terrain.z_max,
            mountain_templates=mountain_templates, mountain_pick=resolve_world_slice(world, WorldReliefPickPolicy, ctx=resolve_ctx).mountain,
            terrain_merge=tuple(TerrainMergeEntry(key=entry.system_terrain, merge_rank=entry.merge_rank)
                for entry in sorted(resolve_world_slice(world, WorldTerrainRegistry, ctx=resolve_ctx).root, key=lambda e: e.system_terrain)))
        return relief

    @staticmethod
    def _routes(world_uid: EntityUid, hydro: WorldHydrology, anchors: tuple[HydrologyAnchorInput, ...],
                terrain: TerrainBaseInput, topology: WorldTopology, mode: ResolutionMode,
                liquid_keys: frozenset[MaterialKey]) -> HydrologyPlanInput:
        routes = HydrologyPlanInput(enabled=hydro.enabled, seed=terrain.seed, resolution_mode=mode,
            scopes=HYDROLOGY_BOOTSTRAP_SCOPES, default_water_level=FineZ(hydro.default_water_level),
            seas=hydro.default_seas, lakes=hydro.default_lakes, rivers=hydro.default_rivers,
            declared_rivers=tuple(hydro.declared_rivers), coastlines=tuple(hydro.declared_coastlines),
            declared_lakes=tuple(hydro.declared_lakes), anchors=anchors, topology=topology, grid=terrain.grid,
            z_min=terrain.z_min, z_max=terrain.z_max, liquid_keys=liquid_keys,
            change_uid=initial_water_change_uid(world_uid))
        return routes

    @staticmethod
    def _river_relief(routes: HydrologyPlanInput) -> RiverReliefInput:
        return RiverReliefInput(z_min=routes.z_min, z_max=routes.z_max, grid=routes.grid, topology=routes.topology,
            channel_depths=tuple((kind, routes.rivers.channel_depth_for(kind)) for kind in sorted(
                (HydrologyConnectionType.RIVER, HydrologyConnectionType.MOUNTAIN_RIVER), key=lambda kind: kind.value)))


def mountain_template_inputs(templates: dict[str, "ReliefTemplate"]) -> tuple[MountainTemplateInput, ...]:
    """Freeze the caller-loaded mountain subset without reading the template store."""
    return tuple(MountainTemplateInput(template_uid=uid, context=body.context, side_recipe=body.side_recipe)
        for uid, body in sorted(templates.items()) if body.context is ReliefContext.MOUNTAIN)
