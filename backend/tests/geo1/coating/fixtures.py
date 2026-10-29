from copy import replace

from app.application.worldData.generators.terrain.relief.surfaceCoatingSupport import SurfaceSupportDependencies
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.application.encoding.canonicalCodec import digest
from app.application.planning.service.planFingerprints import output_fingerprint
from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND
from app.dataModel.climate.enums.climateZone import ClimateZoneProfileData
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan, ResolvedClimateProfile
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, DeclaredWaterPaint
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.policy.policyFacts import KnownFact
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan, MountainLayout, LightReliefPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import ShoreCoatingTarget
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import CoatingPlanInput
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.support_sources.fixtures import captured


def key(slot, fingerprint=b"i" * 32, world="world"):
    return PlanKey(world_uid=world, scope=WorldPlanScope(), contract_id="test." + slot,
                   schema_version=1, algorithm_version=1, input_fingerprint=fingerprint)


def envelope(slot, payload, dependencies=()):
    return PlanEnvelope[type(payload)](ref=PlanRef(key=key(slot), output_fingerprint=output_fingerprint(payload, dependencies, (), SURFACE_MANIFEST)),
        payload=payload, dependencies=dependencies, diagnostics=())


def prepared(inputs=None, entries=(), shores=None, layout_templates=(), light_ravines=()):
    inputs = inputs or captured()
    rows = tuple((SurfaceGridCoord(x, y), 0) for y in range(2) for x in range(2))
    terrain = TerrainPlan(bbox=GridBBox(x_min=0, y_min=0, x_max=1, y_max=1), surface_z=rows)
    light = LightReliefPlan(base_surface_z=(), mountain_cells=(), ravine_cells=(), ravine_terrain="ravine", terrain_merge=())
    # Supply light extent matching coarse without invoking any generation/mill.
    from app.dataModel.spatial.grid.coordinateTypes import LightCellRef
    light = replace(light, base_surface_z=tuple((LightCellRef(c.gx, c.gy, 0, 0), z) for c, z in rows), ravine_cells=light_ravines)
    relief = ReliefPlan(surface_z=rows, light=light, mountain_layout=MountainLayout(entries=entries, templates=layout_templates,
        world_pick=ReliefContextPickPolicy(), terrain_key="mountain"))
    river = RiverReliefPlan(surface_z=rows, fine_surface_z=(), coarse_beds=(), fine_beds=())
    paint = DeclaredWaterPaint(lakes=(), coastlines=(), segments=(), intents=())
    shore = MapCellHydrology.shore(HydrologyShoreKind.SEA, water_body_uid="body").with_water_level(5)
    hydro = HydrologyPlan(coarse_surface_z=rows, coarse_hydro=(), sparse_fine_hydro=shores if shores is not None else (((0, 0), shore),),
        fine_z_overrides=(), water_bodies=(), physical_unions=(), declared_paint=paint)
    climate = ClimateBasePlan(poles=(), bbox=None, default_zone="temperate",
        profiles=(ResolvedClimateProfile(key="temperate", values=ClimateZoneProfileData(15, 0, 50, 10, 10)),), blend=CLIMATE_POLE_BLEND)
    relief_envelope = envelope("relief", relief)
    river_envelope = envelope("river_relief", river, (PlanDependency(slot="relief", ref=relief_envelope.ref),))
    hydro_envelope = envelope("hydrology", hydro, (PlanDependency(slot="river_relief", ref=river_envelope.ref),))
    local_envelope = envelope("climate_local", ClimateLocalPlan(anchors=()), (PlanDependency(slot="hydrology", ref=hydro_envelope.ref),))
    deps = SurfaceSupportDependencies(envelope("climate_base", climate), envelope("terrain_base", terrain),
        relief_envelope, river_envelope, hydro_envelope, local_envelope)
    dependencies = tuple(PlanDependency(slot=name, ref=getattr(deps, name).ref) for name in sorted(deps.__dataclass_fields__))
    request = PlanRequest[type(inputs)](key=key("surface_support", digest(inputs, SURFACE_MANIFEST)), inputs=inputs, dependencies=dependencies)
    return request, deps


def coating_input(mode=ResolutionMode.RUNTIME, target=None):
    return CoatingPlanInput(resolution_mode=mode, default_target=target if target is not None else KnownFact(
        value=ShoreCoatingTarget(terrain="shore", material="sand")), targets=())


def binding(slot, input_type, payload_type):
    from pydantic import TypeAdapter
    from app.application.planning.providers.planProvider import RegisteredPlanContract
    from app.application.cache.contracts.cacheBackend import CacheBinding
    from app.application.worldData.planning.encoding.surfaceEnvelopeCodec import SurfaceEnvelopeCodec
    from app.dataModel.cache.contracts.cacheContract import CacheContract
    from app.dataModel.planning.contracts.planContract import PlanContractMetadata
    return RegisteredPlanContract(
        PlanContractMetadata(id="test." + slot, schema_version=1, algorithm_version=1),
        TypeAdapter(input_type).validate_python, lambda world, scope, inputs, deps: digest(inputs, SURFACE_MANIFEST), (),
        CacheBinding(CacheContract[PlanEnvelope[payload_type]](id="test.cache." + slot, schema_version=1),
                     SurfaceEnvelopeCodec(PlanEnvelope[payload_type], SURFACE_MANIFEST)), SURFACE_MANIFEST)
