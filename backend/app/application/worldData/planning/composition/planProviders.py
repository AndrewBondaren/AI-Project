"""Typed surface handles and baseline provider registration; the engine stays generic."""

from dataclasses import dataclass

from pydantic import TypeAdapter

from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.encoding.canonicalCodec import encode
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanRegistry
from app.application.planning.service.planFingerprints import input_fingerprint
from app.application.worldData.generators.climate.planning.climatePlanProvider import ClimateBasePlanProvider, ClimateLocalPlanProvider
from app.application.worldData.generators.terrain.planning.terrainPlanProvider import TerrainPlanProvider
from app.application.worldData.generators.terrain.planning.waterPlacementPlanProvider import WaterPlacementPlanProvider
from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import ReliefPlanProvider, RiverReliefPlanProvider
from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import HydrologyRoutesPlanProvider, HydrologyFinalPlanProvider
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import HydrologyFactsAssembler
from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.application.worldData.generators.hydrology.load.paint.declaredWaterPaintProjector import DeclaredWaterPaintProjector
from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyRoutesPlan, HydrologyPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput, HydrologyFinalInput
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import PlanScope
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.surfacePlanning.surfacePlanBindings import SurfacePlanBinding, surface_plan_binding
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.application.worldData.planning.encoding.surfaceEnvelopeCodec import SurfaceEnvelopeCodec
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput, CoastlineBoundaryPlan
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan, GeoHydrologyPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import GeoWaterPlacementPlan
from app.dataModel.terrain.regions.regionPlanningInput import TerrainRegionPlanningInput
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput, CoatingPlanInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceSupportPlan, CoatingPlan


def _binding[I, T](slot: SurfacePlanSlot, input_type: type[I], payload_type: type[T]) -> RegisteredPlanContract[I, T]:
    return declared_binding(surface_plan_binding(slot), input_type, payload_type)


def declared_binding[I, T](declaration: SurfacePlanBinding, input_type: type[I],
                           payload_type: type[T]) -> RegisteredPlanContract[I, T]:
    """Bind an explicit domain declaration; no dependency-family inference."""
    metadata = declaration.metadata
    adapter = TypeAdapter[I](input_type)

    def validate(value: object) -> I:
        encode(value, SURFACE_MANIFEST)
        return adapter.validate_python(value, strict=True)

    def fingerprint(world_uid: EntityUid, scope: PlanScope, inputs: I,
                    deps: tuple[PlanDependency, ...]):
        return input_fingerprint(metadata, world_uid, scope, inputs, deps, SURFACE_MANIFEST)

    return RegisteredPlanContract(metadata, validate, fingerprint,
        declaration.dependency_contracts(),
        CacheBinding(CacheContract[PlanEnvelope[T]](
            id=declaration.cache_id, schema_version=declaration.cache_schema_version),
            SurfaceEnvelopeCodec(PlanEnvelope[payload_type], SURFACE_MANIFEST)), SURFACE_MANIFEST)


@dataclass(frozen=True)
class WorldPlanProviders:
    climate_base: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan]
    terrain_base: RegisteredPlanContract[TerrainBaseInput, TerrainPlan]
    water_placement: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan]
    relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan]
    hydrology_routes: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan]
    river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan]
    hydrology: RegisteredPlanContract[HydrologyFinalInput, HydrologyPlan]
    climate_local: RegisteredPlanContract[ClimateLocalInput, ClimateLocalPlan]


@dataclass(frozen=True)
class GeoWorldPlanProviders:
    climate_base: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan]
    terrain_base: RegisteredPlanContract[TerrainBaseInput, TerrainPlan]
    terrain_regions: RegisteredPlanContract[TerrainRegionPlanningInput, TerrainRegionPlan]
    water_placement: RegisteredPlanContract[GeoWaterPlacementInput, GeoWaterPlacementPlan]
    relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan]
    hydrology_routes: RegisteredPlanContract[GeoHydrologyPlanInput, GeoHydrologyRoutesPlan]
    river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan]
    hydrology: RegisteredPlanContract[HydrologyFinalInput, GeoHydrologyPlan]
    climate_local: RegisteredPlanContract[ClimateLocalInput, ClimateLocalPlan]
    coastline_boundaries: RegisteredPlanContract[CoastlineBoundaryInput, CoastlineBoundaryPlan]
    surface_support: RegisteredPlanContract[SurfaceSupportInput, SurfaceSupportPlan]
    coating: RegisteredPlanContract[CoatingPlanInput, CoatingPlan]


def register_world_plan_providers(registry: PlanRegistry) -> WorldPlanProviders:
    S = SurfacePlanSlot
    base = _binding(S.CLIMATE_BASE, ClimateBaseInput, ClimateBasePlan)
    terrain = _binding(S.TERRAIN_BASE, TerrainBaseInput, TerrainPlan)
    water = _binding(S.WATER_PLACEMENT, WaterPlacementInput, WaterPlacementPlan)
    relief = _binding(S.RELIEF, ReliefPlanInput, ReliefPlan)
    routes = _binding(S.HYDROLOGY_ROUTES, HydrologyPlanInput, HydrologyRoutesPlan)
    river = _binding(S.RIVER_RELIEF, RiverReliefInput, RiverReliefPlan)
    final = _binding(S.HYDROLOGY, HydrologyFinalInput, HydrologyPlan)
    local = _binding(S.CLIMATE_LOCAL, ClimateLocalInput, ClimateLocalPlan)
    registry.register(base, ClimateBasePlanProvider())
    registry.register(terrain, TerrainPlanProvider(base))
    registry.register(water, WaterPlacementPlanProvider(terrain))
    registry.register(relief, ReliefPlanProvider(base, terrain, water))
    registry.register(routes, HydrologyRoutesPlanProvider(relief, water, HydrologyRoutesAssembler(
        WaterBodyPlanner(), CoarseRiverPlanner(), FineRiverPlanner(), DeclaredWaterPaintProjector())))
    registry.register(river, RiverReliefPlanProvider(relief, routes))
    registry.register(final, HydrologyFinalPlanProvider(relief, routes, river, HydrologyFactsAssembler()))
    registry.register(local, ClimateLocalPlanProvider(base, final))
    return WorldPlanProviders(base, terrain, water, relief, routes, river, final, local)
