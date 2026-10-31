"""Physical fine water execution; publication and revision binding are separate."""
from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.water.planning.geoExecution import geo_execution_modes, geo_auto_lakes
from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.planning.stages.openWaterPlan import AssembledWater, MaterializedWater, FineWaterResult
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile, SampledFloorProfile
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


class FineWaterJob:
    def fill(self, window: FineSurfaceWindow, inputs: GeoHydrologyPlanInput, *, world_uid: str,
             specs: tuple[BasinSpec, ...], classification_decisions: tuple[tuple[Category, HydrologyGenerationDecision], ...],
             control: PlanBuildControl) -> PlanBuildResult[FineWaterResult]:
        control.raise_if_shutdown()
        window = FineSurfaceWindow.model_validate(window, strict=True)
        topology = fine_topology(inputs.topology, inputs.grid.fine_span)
        if topology != window.topology:
            raise ValueError("fine water requires the exact frozen terrain topology")
        bounds = topology.bounds
        if len(window.surface_z) != bounds.width * bounds.height:
            raise PlanBuildFailure((FieldPathError(("fine_water", "coverage"),
                "physical water resolution requires complete canonical fine terrain evidence"),))
        if any(not inputs.z_min <= z <= inputs.z_max for _, z in window.surface_z):
            raise ValueError("fine elevations exceed captured physical z bounds")
        cells = frozenset(cell for cell, _ in window.surface_z)
        for spec in specs:
            profile = spec.floor_profile
            if spec.liquid not in inputs.liquid_keys:
                raise ValueError("accepted liquid is absent from captured material membership")
            if not spec.footprint <= cells or profile is None:
                raise ValueError("accepted fine basin requires complete footprint and explicit floor profile")
            if ((isinstance(profile, SampledFloorProfile) and profile.space is not CoordinateSpace.WORLD_FINE_GRID)
                    or isinstance(profile, FieldFloorProfile) and profile.recipe.topology != topology):
                raise ValueError("accepted floor profile must use the exact fine terrain frame")
            if not inputs.z_min <= spec.floor_z < spec.z_water_level <= inputs.z_max:
                raise ValueError("accepted floor/level exceed physical z bounds")
        modes = geo_execution_modes(classification_decisions)
        if all(mode is Mode.DISABLED for mode in modes.values()):
            if specs:
                raise PlanBuildFailure((FieldPathError(("classification_decisions",), "disabled water cannot publish accepted basins"),))
            return PlanBuildResult[FineWaterResult](payload=(window, AssembledWater(
                MaterializedWater((), (), (), (), (), SourceBodyMapping(entries=())), ())), diagnostics=())
        scratch = SurfaceHeightmap(world_uid, GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max),
                                   {cell: int(z) for cell, z in window.surface_z})
        apply_basin_z(scratch, specs, topology, reserved=window.protected_cells, coordinate_space=CoordinateSpace.WORLD_FINE_GRID)
        control.raise_if_shutdown()
        diagnostics: list[PlanDiagnostic] = []
        policy = WorldHydrology(default_water_level=inputs.default_water_level,
            default_seas=inputs.seas, default_lakes=inputs.lakes, default_rivers=inputs.rivers)
        water = assemble_water_bodies(scratch, specs, topology, policy, change_uid=inputs.change_uid,
            auto_seas=False, auto_lakes=geo_auto_lakes(inputs, modes), allowed_kinds=inputs.allowed_body_kinds,
            ctx=ResolveContext(collect_only=True, validate_only=inputs.resolution_mode is ResolutionMode.VALIDATE_ONLY),
            emit=diagnostics.append)
        control.raise_if_shutdown()
        errors = tuple(d.issue for d in diagnostics if d.disposition is PlanDiagnosticDisposition.ERROR)
        if errors:
            raise PlanBuildFailure(errors)
        post = FineSurfaceWindow(coverage=window.coverage, topology=topology, protected_cells=window.protected_cells,
            surface_z=tuple(((FineX(x), FineY(y)), FineZ(z)) for (x, y), z in scratch.surface_z.items()))
        return PlanBuildResult[FineWaterResult](payload=(post, water), diagnostics=tuple(dict.fromkeys(diagnostics)))
