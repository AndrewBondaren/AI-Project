"""Publish native final facts with an exact frozen source dependency graph."""
from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.planning.assembly.final.nativeFacts import NativeFinalFactsJob
from app.application.worldData.generators.hydrology.planning.assembly.nativeRoutesPublication import NATIVE_ROUTES_CONTRACT
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FineWaterPublicationJob, FINE_WATER_CONTRACT, PRE_WATER_SURFACE
from app.application.worldData.generators.hydrology.water.planning.geoExecution import geo_execution_decisions
from app.application.worldData.generators.hydrology.rivers.planning.fine.publication import FINE_WATER
from app.application.worldData.generators.terrain.relief.planning.river.publication import NATIVE_RIVER_RELIEF
from app.application.worldData.generators.terrain.planning.preWater.terrainWindowJob import PRE_WATER_WINDOW
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion, PlanKey, PlanSlot
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow


NATIVE_FINAL = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("hydrology.native_final"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1))
ROUTES = PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value)
RIVER = PlanSlot(SurfacePlanSlot.RIVER_RELIEF.value)


class NativeFinalPublicationJob:
    def _admit[T](self, envelope: PlanEnvelope[T], expected: PlanRef, metadata: PlanContractMetadata,
                  world_uid: EntityUid, source: PlanRef) -> None:
        key = envelope.ref.key
        if (envelope.ref != expected or key.world_uid != world_uid or key.scope != source.key.scope
                or (key.contract_id, key.schema_version, key.algorithm_version)
                != (metadata.id, metadata.schema_version, metadata.algorithm_version)
                or envelope.ref.output_fingerprint != output_fingerprint(
                    envelope.payload, envelope.dependencies, envelope.diagnostics, SURFACE_MANIFEST)):
            raise ValueError("native final requires exact expected revisions, contracts and output proofs")

    def publish(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                relief_inputs: RiverReliefInput, specs: tuple[BasinSpec, ...],
                before: PlanEnvelope[FineSurfaceWindow], expected_before: PlanRef,
                water: PlanEnvelope[FineWaterResult], expected_water: PlanRef,
                routes: PlanEnvelope[GeoHydrologyRoutesPlan], expected_routes: PlanRef,
                river: PlanEnvelope[RiverReliefPlan], expected_river: PlanRef,
                control: PlanBuildControl) -> PlanEnvelope[GeoHydrologyPlan]:
        control.raise_if_shutdown()
        before = PlanEnvelope[FineSurfaceWindow].model_validate(before)
        routes = PlanEnvelope[GeoHydrologyRoutesPlan].model_validate(routes)
        river = PlanEnvelope[RiverReliefPlan].model_validate(river)
        self._admit(before, expected_before, PRE_WATER_WINDOW, world_uid, expected_before)
        self._admit(routes, expected_routes, NATIVE_ROUTES_CONTRACT, world_uid, before.ref)
        self._admit(river, expected_river, NATIVE_RIVER_RELIEF, world_uid, before.ref)
        errors = tuple(d.issue for d in before.diagnostics if d.disposition is PlanDiagnosticDisposition.ERROR)
        if errors:
            raise PlanBuildFailure(errors)
        water = FineWaterPublicationJob.admit_result(water, expected_water=expected_water,
            world_uid=world_uid, inputs=inputs, control=control)
        water_refs = {d.slot: d.ref for d in water.dependencies}
        route_deps = (PlanDependency(slot=FINE_WATER, ref=water.ref),)
        river_deps = (*route_deps, PlanDependency(slot=ROUTES, ref=routes.ref))
        if (set(water_refs) != {PRE_WATER_SURFACE, PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value)}
                or water.ref.key.scope != before.ref.key.scope
                or water_refs.get(PRE_WATER_SURFACE) != before.ref or routes.dependencies != route_deps
                or river.dependencies != river_deps):
            raise ValueError("native final requires one exact W/F/routes/river dependency graph")
        decisions = geo_execution_decisions(routes.payload.classification_decisions)
        physical = (inputs, tuple(sorted(specs, key=lambda s: s.source_uid)), decisions)
        for envelope, metadata, captured in ((water, FINE_WATER_CONTRACT, physical),
                (routes, NATIVE_ROUTES_CONTRACT, inputs), (river, NATIVE_RIVER_RELIEF, relief_inputs)):
            if envelope.ref.key.input_fingerprint != input_fingerprint(metadata, world_uid,
                    before.ref.key.scope, captured, envelope.dependencies, SURFACE_MANIFEST):
                raise ValueError("native final captured inputs must match source operation keys")
        if ((inputs.grid, inputs.topology, inputs.z_min, inputs.z_max)
                != (relief_inputs.grid, relief_inputs.topology, relief_inputs.z_min, relief_inputs.z_max)):
            raise ValueError("native final requires the same captured river frame")
        result = NativeFinalFactsJob().assemble(inputs=inputs, before=before.payload, water=water.payload,
            routes=routes.payload, river=river.payload, control=control)
        diagnostics = tuple(dict.fromkeys((*before.diagnostics, *water.diagnostics, *routes.diagnostics,
                                           *river.diagnostics, *result.diagnostics)))
        deps = tuple(sorted((*river_deps, PlanDependency(slot=PRE_WATER_SURFACE, ref=before.ref),
                             PlanDependency(slot=RIVER, ref=river.ref)), key=lambda d: d.slot))
        metadata, scope = NATIVE_FINAL, before.ref.key.scope
        key = PlanKey(world_uid=world_uid, scope=scope, contract_id=metadata.id,
            schema_version=metadata.schema_version, algorithm_version=metadata.algorithm_version,
            input_fingerprint=input_fingerprint(metadata, world_uid, scope, (inputs, relief_inputs), deps, SURFACE_MANIFEST))
        control.raise_if_shutdown()
        return PlanEnvelope[GeoHydrologyPlan](ref=PlanRef(key=key,
            output_fingerprint=output_fingerprint(result.payload, deps, diagnostics, SURFACE_MANIFEST)),
            payload=result.payload, dependencies=deps, diagnostics=diagnostics)
