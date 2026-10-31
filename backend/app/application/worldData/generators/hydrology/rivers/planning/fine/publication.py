"""Publish declared fine routes bound to one resolved fine-water revision."""
from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.rivers.planning.fine.execution import FineRiverJob
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FINE_WATER_CONTRACT
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.hydrology.planning.stages.riverRoutePlans import FineRiverPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion, PlanKey, PlanSlot
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.topology.fineTopology import fine_topology


FINE_RIVER_CONTRACT = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("hydrology.fine_river_routes"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1))
FINE_WATER = PlanSlot("fine_water")


class FineRiverPublicationJob:
    def publish(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                water: PlanEnvelope[FineWaterResult], expected_water: PlanRef,
                control: PlanBuildControl) -> PlanEnvelope[FineRiverPlan]:
        control.raise_if_shutdown()
        inputs = GeoHydrologyPlanInput.model_validate(inputs)
        water = PlanEnvelope[FineWaterResult].model_validate(water)
        key = water.ref.key
        contract = FINE_WATER_CONTRACT
        if (water.ref != expected_water or key.world_uid != world_uid
                or key.contract_id != contract.id or key.schema_version != contract.schema_version
                or key.algorithm_version != contract.algorithm_version
                or water.ref.output_fingerprint != output_fingerprint(
                    water.payload, water.dependencies, water.diagnostics, SURFACE_MANIFEST)):
            raise ValueError("fine routes require the exact published fine-water revision and output proof")
        errors = tuple(d.issue for d in water.diagnostics if d.disposition is PlanDiagnosticDisposition.ERROR)
        if errors:
            raise PlanBuildFailure(errors)
        window, assembled = water.payload
        if window.topology != fine_topology(inputs.topology, inputs.grid.fine_span):
            raise ValueError("fine river inputs must match the published fine-water topology")
        surface = dict(window.surface_z)
        if (any(not inputs.z_min <= z <= inputs.z_max for z in surface.values())
                or any(cell not in surface for cell, _ in assembled.materialized.cells)):
            raise ValueError("fine water facts and heights must lie within the observed fine surface")
        deps = (PlanDependency(slot=FINE_WATER, ref=water.ref),)
        result = FineRiverJob().plan_fine(world_uid=world_uid, inputs=inputs, water=water.payload, control=control)
        diagnostics = tuple(dict.fromkeys((*water.diagnostics, *result.diagnostics)))
        result_key = PlanKey(world_uid=world_uid, scope=key.scope, contract_id=FINE_RIVER_CONTRACT.id,
            schema_version=FINE_RIVER_CONTRACT.schema_version, algorithm_version=FINE_RIVER_CONTRACT.algorithm_version,
            input_fingerprint=input_fingerprint(FINE_RIVER_CONTRACT, world_uid, key.scope, inputs, deps, SURFACE_MANIFEST))
        return PlanEnvelope[FineRiverPlan](ref=PlanRef(key=result_key,
            output_fingerprint=output_fingerprint(result.payload, deps, diagnostics, SURFACE_MANIFEST)),
            dependencies=deps, payload=result.payload, diagnostics=diagnostics)
