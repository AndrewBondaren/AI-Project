"""Publish the admitted native route-stage result against its canonical water source."""
from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.rivers.planning.fine.publication import FINE_WATER
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion, PlanKey
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.registryKey import RegistryKey


NATIVE_ROUTES_CONTRACT = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("hydrology.native_routes"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1))


class NativeRoutesPublicationJob:
    def publish(self, result: PlanBuildResult[GeoHydrologyRoutesPlan], *, world_uid: EntityUid,
                inputs: GeoHydrologyPlanInput, water: PlanRef,
                control: PlanBuildControl) -> PlanEnvelope[GeoHydrologyRoutesPlan]:
        """The caller supplies results already admitted by the water operation."""
        control.raise_if_shutdown()
        deps = (PlanDependency(slot=FINE_WATER, ref=water),)
        metadata, scope = NATIVE_ROUTES_CONTRACT, water.key.scope
        key = PlanKey(world_uid=world_uid, scope=scope, contract_id=metadata.id,
            schema_version=metadata.schema_version, algorithm_version=metadata.algorithm_version,
            input_fingerprint=input_fingerprint(metadata, world_uid, scope, inputs, deps, SURFACE_MANIFEST))
        return PlanEnvelope[GeoHydrologyRoutesPlan](ref=PlanRef(key=key,
            output_fingerprint=output_fingerprint(result.payload, deps, result.diagnostics, SURFACE_MANIFEST)),
            payload=result.payload, dependencies=deps, diagnostics=result.diagnostics)
