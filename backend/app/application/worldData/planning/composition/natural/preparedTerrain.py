"""Standalone natural preparation registration; production surface handles stay unchanged."""
from pydantic import TypeAdapter

from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.encoding.canonicalCodec import encode
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanRegistry
from app.application.planning.service.planFingerprints import input_fingerprint
from app.application.worldData.generators.terrain.planning.preWater.prepared.provider import NaturalTerrainPlanProvider
from app.application.worldData.planning.encoding.surfaceEnvelopeCodec import SurfaceEnvelopeCodec
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.cache.contracts.cacheContract import CacheContract, CacheContractRegistry, CacheSchemaVersion
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency, PlanDependencyContract
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion, PlanSlot, PlanScope
from app.dataModel.registryKey import RegistryKey
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.natural.preparedTerrain import NaturalTerrainInputs, PreparedNaturalTerrain
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan


NATURAL_TERRAIN_CONTRACT = PlanContractMetadata(
    id=RegistryKey[PlanContractRegistry]("terrain.prepared_natural"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1))


def register_natural_terrain(registry: PlanRegistry, *,
    climate: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan],
    terrain: RegisteredPlanContract[TerrainBaseInput, TerrainPlan],
) -> RegisteredPlanContract[NaturalTerrainInputs, PreparedNaturalTerrain]:
    adapter = TypeAdapter[NaturalTerrainInputs](NaturalTerrainInputs)

    def validate(value: object) -> NaturalTerrainInputs:
        encode(value, SURFACE_MANIFEST)
        return adapter.validate_python(value, strict=True)

    def fingerprint(world: EntityUid, scope: PlanScope, inputs: NaturalTerrainInputs,
                    dependencies: tuple[PlanDependency, ...]):
        return input_fingerprint(NATURAL_TERRAIN_CONTRACT, world, scope, inputs, dependencies, SURFACE_MANIFEST)

    declarations = tuple(PlanDependencyContract(slot=PlanSlot(slot.value), contract_id=handle.metadata.id,
        schema_version=handle.metadata.schema_version, algorithm_version=handle.metadata.algorithm_version)
        for slot, handle in ((SurfacePlanSlot.CLIMATE_BASE, climate), (SurfacePlanSlot.TERRAIN_BASE, terrain)))
    binding = RegisteredPlanContract(NATURAL_TERRAIN_CONTRACT, validate, fingerprint, declarations,
        CacheBinding(CacheContract[PlanEnvelope[PreparedNaturalTerrain]](
            id=RegistryKey[CacheContractRegistry]("terrain.envelope.prepared_natural"), schema_version=CacheSchemaVersion(1)),
            SurfaceEnvelopeCodec(PlanEnvelope[PreparedNaturalTerrain], SURFACE_MANIFEST)), SURFACE_MANIFEST)
    registry.register(binding, NaturalTerrainPlanProvider(climate, terrain))
    return binding
