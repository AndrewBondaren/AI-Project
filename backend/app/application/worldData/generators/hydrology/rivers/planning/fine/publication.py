"""Publish declared/proposed fine routes bound to one resolved fine-water revision."""
from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.rivers.planning.fine.execution import FineRiverJob
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FineWaterPublicationJob
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion, PlanKey, PlanSlot
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


FINE_RIVER_CONTRACT = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("hydrology.fine_river_routes"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(2))
FINE_WATER = PlanSlot("fine_water")


class FineRiverPublicationJob:
    """Require successful source water, then publish accepted routes and all issues.

    Routing ERROR diagnostics do not invalidate other accepted routes. Consumers
    must reconcile declared/proposed outcomes explicitly before claiming complete
    river processing; envelope existence is not that proof.
    """

    def publish(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                water: PlanEnvelope[FineWaterResult], expected_water: PlanRef,
                coarse: CoarseRiverPlan,
                control: PlanBuildControl) -> PlanEnvelope[FineRiverPlan]:
        control.raise_if_shutdown()
        inputs = GeoHydrologyPlanInput.model_validate(inputs)
        coarse = CoarseRiverPlan.model_validate(coarse)
        invalid = tuple(FieldPathError(("coarse", route.river_uid), "proposal requires canonical coarse coordinates")
            for route in coarse.routes if any(inputs.topology.canonicalize(cell.gx, cell.gy) != (cell.gx, cell.gy)
                for segment in route.segments for cell in segment.path))
        if invalid:
            raise PlanBuildFailure(invalid)
        water = FineWaterPublicationJob.admit_result(water, expected_water=expected_water,
            world_uid=world_uid, inputs=inputs, control=control)
        key = water.ref.key
        deps = (PlanDependency(slot=FINE_WATER, ref=water.ref),)
        result = FineRiverJob().plan_fine(world_uid=world_uid, inputs=inputs, water=water.payload,
                                         coarse=coarse, control=control)
        diagnostics = tuple(dict.fromkeys((*water.diagnostics, *result.diagnostics)))
        result_key = PlanKey(world_uid=world_uid, scope=key.scope, contract_id=FINE_RIVER_CONTRACT.id,
            schema_version=FINE_RIVER_CONTRACT.schema_version, algorithm_version=FINE_RIVER_CONTRACT.algorithm_version,
            input_fingerprint=input_fingerprint(FINE_RIVER_CONTRACT, world_uid, key.scope,
                (inputs, coarse), deps, SURFACE_MANIFEST))
        return PlanEnvelope[FineRiverPlan](ref=PlanRef(key=result_key,
            output_fingerprint=output_fingerprint(result.payload, deps, diagnostics, SURFACE_MANIFEST)),
            dependencies=deps, payload=result.payload, diagnostics=diagnostics)
