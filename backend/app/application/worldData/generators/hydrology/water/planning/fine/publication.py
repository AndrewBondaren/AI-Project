"""Bind native accepted placement, terrain and physical inputs into one result revision."""
from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.water.planning.fine.execution import FineWaterJob
from app.application.worldData.generators.hydrology.water.planning.geoExecution import geo_execution_decisions
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.placement.result import PlacementBatchResultV2, ResolvedPlacementV2, UnresolvedPlacementV2
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion, PlanKey, PlanSlot
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


FINE_WATER_CONTRACT = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("hydrology.fine_water"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1))
PRE_WATER_SURFACE = PlanSlot("pre_water_surface")


class FineWaterPublicationJob:
    def publish(self, surface: PlanEnvelope[FineSurfaceWindow], *, expected_surface: PlanRef,
                placement: PlanEnvelope[PlacementBatchResultV2], expected_placement: PlanRef,
                inputs: GeoHydrologyPlanInput, specs: tuple[BasinSpec, ...],
                classification_decisions: tuple[tuple[Category, HydrologyGenerationDecision], ...],
                control: PlanBuildControl) -> PlanEnvelope[FineWaterResult]:
        control.raise_if_shutdown()
        classification_decisions = geo_execution_decisions(classification_decisions)
        specs = tuple(sorted(specs, key=lambda spec: spec.source_uid))
        for envelope, expected in ((surface, expected_surface), (placement, expected_placement)):
            if envelope.ref != expected or envelope.ref.output_fingerprint != output_fingerprint(
                    envelope.payload, envelope.dependencies, envelope.diagnostics, SURFACE_MANIFEST):
                raise ValueError("fine water requires exact expected terrain/placement revisions and output proofs")
        errors = tuple(d.issue for d in (*surface.diagnostics, *placement.diagnostics)
                       if d.disposition is PlanDiagnosticDisposition.ERROR)
        if errors:
            raise PlanBuildFailure(errors)
        refs = {d.slot: d.ref for d in surface.dependencies}
        if set(refs) != {SurfacePlanSlot.CLIMATE_BASE, SurfacePlanSlot.TERRAIN_BASE} or any(
                ref.key.world_uid != surface.ref.key.world_uid or ref.key.scope != surface.ref.key.scope for ref in refs.values()):
            raise ValueError("fine water requires coherent frozen climate/terrain dependencies")
        batch = placement.payload
        unresolved = tuple(FieldPathError(("placement", outcome.identity.source_uid),
            "full fine water publication requires resolved placement evidence")
            for outcome in batch.results if isinstance(outcome, UnresolvedPlacementV2))
        if unresolved:
            raise PlanBuildFailure(unresolved)
        declared = {d.slot: d.ref for d in placement.dependencies}
        if (placement.ref.key.world_uid != surface.ref.key.world_uid or batch.world_uid != surface.ref.key.world_uid
                or placement.ref.key.scope != surface.ref.key.scope
                or declared.get(PRE_WATER_SURFACE) != surface.ref
                or batch.snapshot_revision != surface.ref.output_fingerprint):
            raise ValueError("accepted placement must bind the same world/scope/pre-hydrology snapshot")
        accepted = {outcome.identity.source_uid: outcome for outcome in batch.results if isinstance(outcome, ResolvedPlacementV2)}
        if (len(accepted) != sum(isinstance(outcome, ResolvedPlacementV2) for outcome in batch.results)
                or len({s.source_uid for s in specs}) != len(specs)) or any(
                spec.source_uid not in accepted or spec.footprint != accepted[spec.source_uid].footprint.cells for spec in specs):
            raise ValueError("fine basins must match native accepted source identities and footprints")
        dependencies = (PlanDependency(slot=PRE_WATER_SURFACE, ref=surface.ref),
                        PlanDependency(slot=PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value), ref=placement.ref))
        key = PlanKey(world_uid=surface.ref.key.world_uid, scope=surface.ref.key.scope, contract_id=FINE_WATER_CONTRACT.id,
            schema_version=FINE_WATER_CONTRACT.schema_version, algorithm_version=FINE_WATER_CONTRACT.algorithm_version,
            input_fingerprint=input_fingerprint(FINE_WATER_CONTRACT, surface.ref.key.world_uid, surface.ref.key.scope,
                (inputs, specs, classification_decisions), dependencies, SURFACE_MANIFEST))
        result = FineWaterJob().fill(surface.payload, inputs, world_uid=surface.ref.key.world_uid,
                                    specs=specs, classification_decisions=classification_decisions, control=control)
        return PlanEnvelope[FineWaterResult](ref=PlanRef(key=key,
            output_fingerprint=output_fingerprint(result.payload, dependencies, result.diagnostics, SURFACE_MANIFEST)),
            dependencies=dependencies, payload=result.payload, diagnostics=result.diagnostics)
