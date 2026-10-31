"""Bind native river beds to the exact water and route-stage revisions."""
from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.planning.assembly.nativeRoutesPublication import NATIVE_ROUTES_CONTRACT
from app.application.worldData.generators.hydrology.rivers.planning.fine.publication import FINE_WATER
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FineWaterPublicationJob
from app.application.worldData.generators.terrain.relief.planning.river.execution import NativeRiverReliefJob
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion, PlanKey, PlanSlot
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan


NATIVE_RIVER_RELIEF = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("terrain.native_river_relief"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1))


class NativeRiverReliefPublicationJob:
    def publish(self, inputs: RiverReliefInput, *, world_uid: EntityUid,
                routing_inputs: GeoHydrologyPlanInput, water: PlanEnvelope[FineWaterResult],
                expected_water: PlanRef, routes: PlanEnvelope[GeoHydrologyRoutesPlan],
                expected_routes: PlanRef, control: PlanBuildControl) -> PlanEnvelope[RiverReliefPlan]:
        control.raise_if_shutdown()
        inputs = RiverReliefInput.model_validate(inputs)
        routing_inputs = GeoHydrologyPlanInput.model_validate(routing_inputs)
        routes = PlanEnvelope[GeoHydrologyRoutesPlan].model_validate(routes)
        if ((inputs.grid, inputs.topology, inputs.z_min, inputs.z_max)
                != (routing_inputs.grid, routing_inputs.topology, routing_inputs.z_min, routing_inputs.z_max)):
            raise ValueError("native river relief must use the captured routing frame and z bounds")
        key, contract = routes.ref.key, NATIVE_ROUTES_CONTRACT
        source_deps = (PlanDependency(slot=FINE_WATER, ref=expected_water),)
        if (routes.ref != expected_routes or key.world_uid != world_uid
                or key.scope != expected_water.key.scope or key.contract_id != contract.id
                or key.schema_version != contract.schema_version or key.algorithm_version != contract.algorithm_version
                or routes.dependencies != source_deps
                or key.input_fingerprint != input_fingerprint(contract, world_uid, key.scope,
                    routing_inputs, source_deps, SURFACE_MANIFEST)
                or routes.ref.output_fingerprint != output_fingerprint(
                    routes.payload, routes.dependencies, routes.diagnostics, SURFACE_MANIFEST)):
            raise ValueError("native river relief requires exact source-bound native routes and input/output proofs")
        water = FineWaterPublicationJob.admit_result(water, expected_water=expected_water,
            world_uid=world_uid, inputs=routing_inputs, control=control)
        materialized = water.payload[1].materialized
        if (routes.payload.base.water_bodies != materialized.bodies
                or routes.payload.base.physical_unions != water.payload[1].physical_unions
                or routes.payload.source_mapping != materialized.source_mapping):
            raise ValueError("native route water identities must match the canonical source")
        payload = NativeRiverReliefJob().plan(inputs, world_uid=world_uid,
            water=water.payload, routes=routes.payload, control=control)
        deps = (PlanDependency(slot=FINE_WATER, ref=water.ref),
                PlanDependency(slot=PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value), ref=routes.ref))
        diagnostics = tuple(dict.fromkeys((*water.diagnostics, *routes.diagnostics)))
        metadata = NATIVE_RIVER_RELIEF
        result_key = PlanKey(world_uid=world_uid, scope=key.scope, contract_id=metadata.id,
            schema_version=metadata.schema_version, algorithm_version=metadata.algorithm_version,
            input_fingerprint=input_fingerprint(metadata, world_uid, key.scope, inputs, deps, SURFACE_MANIFEST))
        control.raise_if_shutdown()
        return PlanEnvelope[RiverReliefPlan](ref=PlanRef(key=result_key,
            output_fingerprint=output_fingerprint(payload, deps, diagnostics, SURFACE_MANIFEST)),
            payload=payload, dependencies=deps, diagnostics=diagnostics)
