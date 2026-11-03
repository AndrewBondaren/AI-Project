"""Bind a native pre-relief placement batch to its observed terrain and regions."""

from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.water.planning.fine.publication import PRE_WATER_SURFACE
from app.application.worldData.generators.terrain.planning.preWater.terrainWindowJob import PRE_WATER_WINDOW
from app.application.worldData.planning.encoding.surfaceEnvelopeCodec import SurfaceEnvelopeCodec
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.planning.contracts.planContract import PlanContractMetadata
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding, surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.natural.preparedTerrain import NATURAL_TERRAIN_CONTRACT, PREPARED_NATURAL
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.fineTopology import fine_topology


def _require_contract(ref: PlanRef, contract: PlanContractMetadata) -> None:
    key = ref.key
    if (key.contract_id, key.schema_version, key.algorithm_version) != (
            contract.id, contract.schema_version, contract.algorithm_version):
        raise ValueError("placement dependency contract or version mismatch")


def admit_native_placement_dependencies(*, batch: PlacementBatchV2, before: PlanEnvelope[FineSurfaceWindow],
        expected_before: PlanRef, regions: PlanEnvelope[TerrainRegionPlan], expected_regions: PlanRef,
        inputs: GeoWaterPlacementInput, control: PlanBuildControl) -> tuple[PlanDependency, PlanDependency]:
    control.raise_if_shutdown()
    batch = PlacementBatchV2.model_validate(batch, strict=True)
    before = SurfaceEnvelopeCodec(PlanEnvelope[FineSurfaceWindow], SURFACE_MANIFEST).validate(before)
    regions = SurfaceEnvelopeCodec(PlanEnvelope[TerrainRegionPlan], SURFACE_MANIFEST).validate(regions)
    region_slot = SurfacePlanSlot.TERRAIN_REGIONS
    key = before.ref.key
    for envelope, expected, contract in (
        (before, expected_before, PRE_WATER_WINDOW),
        (regions, expected_regions, geo_surface_plan_binding(region_slot).metadata),
    ):
        control.raise_if_shutdown()
        if envelope.ref != expected:
            raise ValueError("placement requires the exact expected dependency revision")
        _require_contract(envelope.ref, contract)
        if envelope.ref.key.world_uid != batch.world_uid or envelope.ref.key.scope != key.scope:
            raise ValueError("placement dependencies must share batch world and plan scope")
        if envelope.ref.output_fingerprint != output_fingerprint(
                envelope.payload, envelope.dependencies, envelope.diagnostics, SURFACE_MANIFEST):
            raise ValueError("placement dependency output proof mismatch")
    errors = tuple(d.issue for e in (before, regions) for d in e.diagnostics
                   if d.disposition is PlanDiagnosticDisposition.ERROR)
    if errors:
        raise PlanBuildFailure(errors)

    contracts = {slot.value: surface_plan_binding(slot).metadata
                 for slot in (SurfacePlanSlot.CLIMATE_BASE, SurfacePlanSlot.TERRAIN_BASE)}
    contracts[PREPARED_NATURAL] = NATURAL_TERRAIN_CONTRACT
    if regions.dependencies or {d.slot for d in before.dependencies} != contracts.keys():
        raise ValueError("unexpected placement upstream dependency slots")
    for dependency in before.dependencies:
        _require_contract(dependency.ref, contracts[dependency.slot])
        upstream = dependency.ref.key
        if upstream.world_uid != key.world_uid or upstream.scope != key.scope:
            raise ValueError("pre-water upstream world or scope mismatch")
    window = before.payload
    if key.input_fingerprint != input_fingerprint(PRE_WATER_WINDOW, key.world_uid, key.scope,
            window.coverage, before.dependencies, SURFACE_MANIFEST):
        raise ValueError("pre-water coverage input proof mismatch")

    snapshot = regions.payload.snapshot
    if batch.phase is not PlacementPhase.PRE_RELIEF or batch.accepted:
        raise ValueError("native water placement requires a joint pre-relief batch")
    if (batch.snapshot_revision != before.ref.output_fingerprint or batch.snapshot_uid != snapshot.snapshot_uid
            or batch.world_uid != snapshot.world_uid):
        raise ValueError("placement batch does not bind the terrain revision and region snapshot")
    if batch.topology != window.topology or window.topology != fine_topology(inputs.topology, inputs.grid.fine_span):
        raise ValueError("placement batch and pre-water window require the captured fine frame")
    bounds = window.topology.bounds
    if len(window.surface_z) != bounds.width * bounds.height:
        raise ValueError("placement requires complete fine window coverage")
    for _, z in window.surface_z:
        control.raise_if_shutdown()
        if not inputs.z_min <= z <= inputs.z_max:
            raise ValueError("pre-water height outside captured vertical bounds")
    for coverage in regions.payload.coverages:
        for span in coverage.spans:
            control.raise_if_shutdown()
            if not (bounds.y_min <= span.y <= bounds.y_max and bounds.x_min <= span.x0 < span.x1 <= bounds.x_max + 1):
                raise ValueError("region span outside pre-water fine bounds")
    control.raise_if_shutdown()
    return (PlanDependency(slot=PRE_WATER_SURFACE, ref=before.ref),
            PlanDependency(slot=PlanSlot(region_slot.value), ref=regions.ref))
