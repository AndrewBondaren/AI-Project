"""Shared frozen upstream evidence for the final→local→support→coating seam."""

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.service.cacheService import CacheService
from app.application.encoding.canonicalCodec import digest
from app.application.planning.providers.planRegistry import PlanRegistry, PlanDependencyReader
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.planning.service.planningService import PlanningService
from app.application.worldData.generators.climate.planning.climatePlanProvider import ClimateLocalPlanProvider
from app.application.worldData.generators.terrain.relief.surfaceCoatingSupport import SurfaceCoatingSupportProvider, CoatingPlanProvider
from app.application.worldData.planning.composition.planProviders import declared_binding
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput, ClimateFeaturePolicy
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot as S
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceSupportPlan, CoatingPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput, CoatingPlanInput
from tests.geo1.coating.fixtures import prepared, coating_input


class Wait:
    def raise_if_cancelled(self):
        pass

    def remaining_seconds(self):
        return 30.0


class FrozenUpstream:
    def build(self, *args):
        raise AssertionError("this seam consumes captured upstream evidence")


def seal(handle, payload, upstream=()):
    deps = tuple(sorted((PlanDependency(slot=slot, ref=envelope.ref) for slot, envelope in upstream), key=lambda d: d.slot))
    meta = handle.metadata
    return PlanEnvelope[type(payload)](ref=PlanRef(key=PlanKey(world_uid="world", scope=WorldPlanScope(),
        contract_id=meta.id, schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
        input_fingerprint=digest(payload, SURFACE_MANIFEST)),
        output_fingerprint=output_fingerprint(payload, deps, (), SURFACE_MANIFEST)),
        payload=payload, dependencies=deps, diagnostics=())


class Seam:
    def __init__(self):
        self.registry = PlanRegistry()
        self.handles = {}
        pairs = ((S.CLIMATE_BASE, ClimateBaseInput, ClimateBasePlan),
            (S.TERRAIN_BASE, TerrainBaseInput, TerrainPlan), (S.RELIEF, ReliefPlanInput, ReliefPlan),
            (S.RIVER_RELIEF, RiverReliefInput, RiverReliefPlan),
            (S.HYDROLOGY, HydrologyFinalInput, GeoHydrologyPlan),
            (S.CLIMATE_LOCAL, ClimateLocalInput, ClimateLocalPlan),
            (S.SURFACE_SUPPORT, SurfaceSupportInput, SurfaceSupportPlan),
            (S.COATING, CoatingPlanInput, CoatingPlan))
        for slot, input_type, output_type in pairs:
            self.handles[slot.value] = declared_binding(geo_surface_plan_binding(slot), input_type, output_type)
        h = self.handles
        for name in ("climate_base", "terrain_base", "relief", "river_relief", "hydrology"):
            self.registry.register(h[name], FrozenUpstream())
        self.registry.register(h["climate_local"], ClimateLocalPlanProvider(h["climate_base"], h["hydrology"]))
        self.registry.register(h["surface_support"], SurfaceCoatingSupportProvider(**{
            name: h[name] for name in ("climate_base", "terrain_base", "relief", "river_relief", "hydrology", "climate_local")}))
        self.registry.register(h["coating"], CoatingPlanProvider(h["surface_support"], h["hydrology"], fine_span=2))
        cache = CachePolicy(max_retained_bytes=10000000, max_entry_bytes=5000000)
        self.service = PlanningService(self.registry, CacheService(MemoryCache(cache), cache),
            PlanningExecutionPolicy(max_workers=2, max_pending_builds=8))
        request, captured = prepared()
        self.support_input = request.inputs
        self.upstream = {}
        for name in ("climate_base", "terrain_base", "relief", "river_relief"):
            deps = (("relief", self.upstream["relief"]),) if name == "river_relief" else ()
            self.upstream[name] = seal(h[name], getattr(captured, name).payload, deps)
        self.common_hydro = {name: getattr(captured.hydrology.payload, name)
                             for name in type(captured.hydrology.payload).model_fields}
        self.local_input = ClimateLocalInput(manual=(), admin=(), feature_policy=ClimateFeaturePolicy(
            synthetic_surface_terrain="plain", water_feature_terrain="water"))

    def final(self, *, source="source", changes=None, decisions=()):
        payload = GeoHydrologyPlan(**(self.common_hydro | (changes or {})),
            source_mapping=SourceBodyMapping(entries=(SourceBodyMappingEntry(source_uid=source, body_uids=()),)),
            classification_decisions=decisions)
        return seal(self.handles["hydrology"], payload,
            (("relief", self.upstream["relief"]), ("river_relief", self.upstream["river_relief"])))

    def build(self, name, inputs, available):
        handle = self.handles[name]
        reader = PlanDependencyReader(self.registry)
        deps = []
        for declaration in handle.dependency_contracts:
            slot = declaration.slot
            envelope = available[slot]
            reader = reader.with_plan(slot, self.handles[slot], envelope)
            deps.append(PlanDependency(slot=slot, ref=envelope.ref))
        deps = tuple(sorted(deps, key=lambda d: d.slot))
        meta = handle.metadata
        request = PlanRequest[type(inputs)](key=PlanKey(world_uid="world", scope=WorldPlanScope(),
            contract_id=meta.id, schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=handle.fingerprint_inputs("world", WorldPlanScope(), inputs, deps)),
            inputs=inputs, dependencies=deps)
        return self.service.get_or_build(handle, request, reader, wait=Wait())

    def run(self, final):
        available = self.upstream | {"hydrology": final}
        for name, inputs in (("climate_local", self.local_input), ("surface_support", self.support_input),
                             ("coating", coating_input())):
            available[name] = self.build(name, inputs, available)
        return available
