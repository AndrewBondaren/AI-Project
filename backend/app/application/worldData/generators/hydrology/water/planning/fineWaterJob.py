"""Accepted fine basin execution on exact frozen terrain evidence."""

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.waterBodyAssembler import AssembledWater, assemble_water_bodies
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile, SampledFloorProfile
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class FineWaterJob:
    """Hydrology owns proof checks and delegates carve/physical water to their owners."""

    def fill(self, surface: PlanEnvelope[FineSurfaceWindow], *, expected_surface: PlanRef,
             topology: WorldTopology, specs: tuple[BasinSpec, ...],
             policy: WorldHydrology, change_uid: EntityUid,
             control: PlanBuildControl) -> tuple[SurfaceHeightmap, AssembledWater, tuple[PlanDiagnostic, ...]]:
        control.raise_if_shutdown()
        if surface.ref != expected_surface or surface.ref.output_fingerprint != output_fingerprint(
                surface.payload, surface.dependencies, surface.diagnostics, SURFACE_MANIFEST):
            raise ValueError("fine water requires the exact expected terrain window revision")
        dependencies = {d.slot: d.ref for d in surface.dependencies}
        if set(dependencies) != {SurfacePlanSlot.CLIMATE_BASE, SurfacePlanSlot.TERRAIN_BASE} or any(
                ref.key.world_uid != surface.ref.key.world_uid or ref.key.scope != surface.ref.key.scope
                for ref in dependencies.values()):
            raise ValueError("fine water requires coherent frozen climate/terrain dependencies")
        window = FineSurfaceWindow.model_validate(surface.payload, strict=True)
        if topology != window.topology:
            raise ValueError("fine water requires the exact frozen terrain topology")
        bounds = topology.bounds
        if len(window.surface_z) != bounds.width * bounds.height or any(
                topology.canonicalize(*cell) != cell for cell, _ in window.surface_z):
            raise PlanBuildFailure((FieldPathError(("fine_water", "coverage"),
                "physical water resolution requires complete canonical fine terrain evidence"),))
        cells = frozenset(cell for cell, _ in window.surface_z)
        if len({s.source_uid for s in specs}) != len(specs):
            raise ValueError("fine water requires unique accepted source UIDs")
        for spec in specs:
            profile = spec.floor_profile
            if not spec.footprint <= cells or profile is None:
                raise ValueError("accepted fine basin requires complete footprint and explicit floor profile")
            if ((isinstance(profile, SampledFloorProfile) and profile.space is not CoordinateSpace.WORLD_FINE_GRID)
                    or isinstance(profile, FieldFloorProfile) and profile.recipe.topology != topology):
                raise ValueError("accepted floor profile must use the exact fine terrain frame")
        control.raise_if_shutdown()
        scratch = SurfaceHeightmap(surface.ref.key.world_uid,
            GridBBox(x_min=bounds.x_min, x_max=bounds.x_max, y_min=bounds.y_min, y_max=bounds.y_max),
            {cell: int(z) for cell, z in window.surface_z})
        apply_basin_z(scratch, specs, topology, reserved=window.protected_cells, coordinate_space=CoordinateSpace.WORLD_FINE_GRID)
        control.raise_if_shutdown()
        diagnostics: list[PlanDiagnostic] = []
        ctx = ResolveContext(collect_only=True)
        water = assemble_water_bodies(scratch, specs, topology, policy, change_uid=change_uid,
            auto_seas=False, auto_lakes=False, ctx=ctx, emit=diagnostics.append)
        control.raise_if_shutdown()
        return scratch, water, tuple(dict.fromkeys(diagnostics))
