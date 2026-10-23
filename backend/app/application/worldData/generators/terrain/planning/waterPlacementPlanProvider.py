"""Existing pre-relief water placement over a frozen terrain dependency."""

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.coordinates.convert import fine_to_grid_xy
from app.application.worldData.generators.hydrology.placement.waterPlacementPass import run_prepared_water_placement
from app.application.worldData.placement.adapters.waterTypes import WaterPlacementContext, WaterPreparationCode
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.placement import PlacementIssueCode
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.ids import UidKind, entity_uid


class WaterPlacementPlanProvider:
    def __init__(self, terrain_base: RegisteredPlanContract[TerrainBaseInput, TerrainPlan]) -> None:
        self._terrain_base = terrain_base

    def build(self, request: PlanRequest[WaterPlacementInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[WaterPlacementPlan]:
        control.raise_if_shutdown()
        terrain = dependencies.require(PlanSlot(SurfacePlanSlot.TERRAIN_BASE.value), self._terrain_base)
        inputs = request.inputs
        if not inputs.enabled or not (inputs.basins or inputs.coastlines or inputs.declared_lakes):
            return PlanBuildResult[WaterPlacementPlan](payload=WaterPlacementPlan(
                coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID, topology=inputs.topology,
                records=(), basin_specs=()), diagnostics=())

        bounds, box = inputs.topology.bounds, terrain.payload.bbox
        if ((box.x_min, box.x_max, box.y_min, box.y_max)
                != (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max)
                or any(not inputs.z_min <= z <= inputs.z_max for _, z in terrain.payload.surface_z)):
            raise PlanBuildFailure((FieldPathError(path=(SurfacePlanSlot.TERRAIN_BASE.value,),
                code=WaterPreparationCode.SNAPSHOT.value,
                message="terrain dependency must cover the water topology and respect captured world z bounds"),))

        anchors: dict[str, Coord] = {}
        subtypes: dict[str, GeographicSubtype] = {}
        for anchor in inputs.anchors:
            point = inputs.topology.canonicalize(*fine_to_grid_xy(*anchor.position, inputs.grid.fine_span))
            if point is not None:
                anchors[anchor.source_uid] = point
            if anchor.subtype is not None:
                subtypes[anchor.source_uid] = anchor.subtype
        # A private legacy POJO is only a transient adapter; no mutable root enters the cache.
        pojo = WorldHydrology(enabled=inputs.enabled, default_water_level=inputs.default_water_level,
            default_seas=inputs.seas, default_lakes=inputs.lakes, declared_basins=list(inputs.basins),
            declared_coastlines=list(inputs.coastlines), declared_lakes=list(inputs.declared_lakes))
        context = WaterPlacementContext(
            world_uid=request.key.world_uid,
            snapshot_uid=entity_uid(request.key.world_uid, UidKind.TERRAIN_SNAPSHOT, phase="pre_relief"),
            snapshot_revision=terrain.ref.output_fingerprint, topology=inputs.topology,
            surface_z={(coord.gx, coord.gy): z for coord, z in terrain.payload.surface_z},
            z_min=inputs.z_min, anchors=anchors, location_subtypes=subtypes,
            auto_specificity={}, dependencies={}, permitted_overlaps={}, separations={})
        ctx = ResolveContext(validate_only=inputs.resolution_mode == ResolutionMode.VALIDATE_ONLY,
                             collect_only=True)
        try:
            result = run_prepared_water_placement(pojo, context, fine_span=inputs.grid.fine_span, ctx=ctx)
        except UnresolvedModelError as error:
            raise PlanBuildFailure(tuple(error.issues)) from error
        control.raise_if_shutdown()
        fallback_codes = {code.value for code in (WaterPreparationCode.CAP_REACHED,
            WaterPreparationCode.KIND_MISMATCH, WaterPreparationCode.DEGENERATE_RING,
            WaterPreparationCode.MERGED_SOURCES)} | {PlacementIssueCode.COASTLINE_PRIORITY_LOWERED.value}
        diagnostics = tuple(PlanDiagnostic(issue=issue, disposition=(
            PlanDiagnosticDisposition.FALLBACK if issue.code in fallback_codes else PlanDiagnosticDisposition.ERROR))
            for issue in dict.fromkeys(ctx.errors))
        plan = WaterPlacementPlan(coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID,
            topology=result.topology, records=result.records, basin_specs=result.basin_specs)
        return PlanBuildResult[WaterPlacementPlan](payload=plan, diagnostics=diagnostics)
