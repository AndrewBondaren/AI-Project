"""Admit one prepared source and publish its requested union as a frozen window."""

from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.terrain.planning.preWater.prepared.materialization import NaturalWindowJob
from app.application.worldData.planning.encoding.surfaceEnvelopeCodec import SurfaceEnvelopeCodec
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.registryKey import RegistryKey
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import AlgorithmVersion, PlanKey, SchemaVersion
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.natural.preparedTerrain import (
    NATURAL_TERRAIN_CONTRACT, PREPARED_NATURAL, PreparedNaturalTerrain,
)
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow


PRE_WATER_WINDOW = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("terrain.pre_water_window"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(2))


class PreWaterTerrainWindowJob:
    def prepare(self, prepared: PlanEnvelope[PreparedNaturalTerrain], *, expected_preparation: PlanRef,
                cells: RegionCoverage, control: PlanBuildControl) -> PlanEnvelope[FineSurfaceWindow]:
        """Admission is per publication union, outside bounded materialization workers."""
        control.raise_if_shutdown()
        key, contract = prepared.ref.key, NATURAL_TERRAIN_CONTRACT
        if (prepared.ref != expected_preparation or key.contract_id != contract.id
                or key.schema_version != contract.schema_version or key.algorithm_version != contract.algorithm_version):
            raise ValueError("fine window requires the exact expected natural preparation revision")
        prepared = SurfaceEnvelopeCodec(PlanEnvelope[PreparedNaturalTerrain], SURFACE_MANIFEST).validate(prepared)
        if prepared.ref.output_fingerprint != output_fingerprint(
                prepared.payload, prepared.dependencies, prepared.diagnostics, SURFACE_MANIFEST):
            raise ValueError("natural preparation revision output proof mismatch")
        errors = tuple(d.issue for d in prepared.diagnostics if d.disposition is PlanDiagnosticDisposition.ERROR)
        if errors:
            raise PlanBuildFailure(errors)
        if ({d.slot for d in prepared.dependencies} != {SurfacePlanSlot.CLIMATE_BASE, SurfacePlanSlot.TERRAIN_BASE}
                or any(d.ref.key.world_uid != key.world_uid or d.ref.key.scope != key.scope
                       for d in prepared.dependencies)):
            raise ValueError("natural preparation requires coherent frozen climate/terrain dependencies")
        control.raise_if_shutdown()
        payload = NaturalWindowJob().materialize(prepared.payload, cells, control)
        dependencies = tuple(sorted((*prepared.dependencies, PlanDependency(slot=PREPARED_NATURAL, ref=prepared.ref)),
                                    key=lambda d: d.slot.encode("utf-8")))
        result_key = PlanKey(world_uid=key.world_uid, scope=key.scope, contract_id=PRE_WATER_WINDOW.id,
            schema_version=PRE_WATER_WINDOW.schema_version, algorithm_version=PRE_WATER_WINDOW.algorithm_version,
            input_fingerprint=input_fingerprint(PRE_WATER_WINDOW, key.world_uid, key.scope,
                payload.coverage, dependencies, SURFACE_MANIFEST))
        control.raise_if_shutdown()
        return PlanEnvelope[FineSurfaceWindow](ref=PlanRef(key=result_key,
            output_fingerprint=output_fingerprint(payload, dependencies, prepared.diagnostics, SURFACE_MANIFEST)),
            dependencies=dependencies, payload=payload, diagnostics=prepared.diagnostics)
