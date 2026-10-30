"""Publish the captured natural recipe as one frozen terrain window."""

from app.application.planning.service.planFingerprints import input_fingerprint, output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.planning.preWater.terrainBaseJob import PreWaterTerrainJob
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.registryKey import RegistryKey
from app.dataModel.planning.contracts.planContract import PlanContractMetadata, PlanContractRegistry
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import AlgorithmVersion, PlanKey, PlanSlot, SchemaVersion
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.fineTopology import fine_topology


# Encoding/algorithm identity, independent of production phase registration.
PRE_WATER_WINDOW = PlanContractMetadata(id=RegistryKey[PlanContractRegistry]("terrain.pre_water_window"),
    schema_version=SchemaVersion(1), algorithm_version=AlgorithmVersion(1))


class PreWaterTerrainWindowJob:
    def prepare(self, world_uid: EntityUid, base_input: TerrainBaseInput, relief_input: ReliefPlanInput,
                support_input: SurfaceSupportInput, climate_base: PlanEnvelope[ClimateBasePlan],
                terrain_base: PlanEnvelope[TerrainPlan], cells: RegionCoverage,
                control: PlanBuildControl) -> PlanEnvelope[FineSurfaceWindow]:
        surface, protected = PreWaterTerrainJob(world_uid, base_input, relief_input, support_input,
                                              climate_base, terrain_base, control).prepare(cells)
        payload = FineSurfaceWindow(coverage=cells, protected_cells=protected,
            topology=fine_topology(support_input.topology, base_input.grid.fine_span), surface_z=tuple(
            ((FineX(x), FineY(y)), FineZ(z)) for (x, y), z in surface.surface_z.items()))
        dependencies = (PlanDependency(slot=PlanSlot(SurfacePlanSlot.CLIMATE_BASE.value), ref=climate_base.ref),
                        PlanDependency(slot=PlanSlot(SurfacePlanSlot.TERRAIN_BASE.value), ref=terrain_base.ref))
        key = PlanKey(world_uid=world_uid, scope=terrain_base.ref.key.scope, contract_id=PRE_WATER_WINDOW.id,
            schema_version=PRE_WATER_WINDOW.schema_version, algorithm_version=PRE_WATER_WINDOW.algorithm_version,
            input_fingerprint=input_fingerprint(PRE_WATER_WINDOW, world_uid, terrain_base.ref.key.scope,
                (base_input, relief_input, support_input, cells), dependencies, SURFACE_MANIFEST))
        control.raise_if_shutdown()
        return PlanEnvelope[FineSurfaceWindow](ref=PlanRef(key=key,
            output_fingerprint=output_fingerprint(payload, dependencies, (), SURFACE_MANIFEST)),
            dependencies=dependencies, payload=payload, diagnostics=())
