"""Final native facts from admitted canonical water and actual river beds."""
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.coordinates.light.grid import light_cell_center_fine
from app.application.worldData.generators.hydrology.planning.assembly.final.riverFacts import river_roles, require_receivers
from app.application.worldData.generators.terrain.planning.projection.coarseSurface import CoarseSurfaceProjectionJob
from app.application.worldData.generators.terrain.planning.projection.heightDelta import FineHeightDeltaJob
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow


class NativeFinalFactsJob:
    def assemble(self, *, inputs: GeoHydrologyPlanInput, before: FineSurfaceWindow,
                 water: FineWaterResult, routes: GeoHydrologyRoutesPlan, river: RiverReliefPlan,
                 control: PlanBuildControl) -> PlanBuildResult[GeoHydrologyPlan]:
        """Publication must admit exact envelopes; this operation proves only joined facts."""
        control.raise_if_shutdown()
        window, assembled = water
        source = assembled.materialized
        if (routes.base.water_bodies != source.bodies or routes.base.physical_unions != assembled.physical_unions
                or routes.source_mapping != source.source_mapping or river.coarse_beds):
            raise ValueError("native final requires canonical water identities and fine-only actual beds")
        delta = FineHeightDeltaJob().compute(before, window, samples=routes.base.fine_base_surface_z,
                                             river=river, control=control)
        surface = CoarseSurfaceProjectionJob().project(window, topology=inputs.topology,
            grid=inputs.grid, overlay=river.fine_surface_z, control=control)
        if surface.surface_z != river.surface_z:
            raise ValueError("native final coarse heights must project actual fine geometry")
        fine = dict(source.cells)
        roles = river_roles(routes.base.fine_routes, river.fine_beds, river.fine_surface_z,
                            lambda cell: cell, control)
        if any(cell in fine and fine[cell].liquid_candidate for cell in roles):
            raise ValueError("river beds cannot replace canonical open-water facts")
        fine.update(roles)
        require_receivers(routes.base.fine_routes, fine, lambda cell: cell)
        if not inputs.enabled and (fine or source.bodies or assembled.physical_unions):
            raise ValueError("disabled hydrology cannot consume active facts")
        scale = LightGridScale.from_tile(inputs.grid.fine_span, 1)
        coarse = []
        for cell, _ in surface.surface_z:
            control.raise_if_shutdown()
            sample = light_cell_center_fine(cell.gx, cell.gy, 0, 0, scale)
            if sample in fine:
                coarse.append((cell, fine[sample]))
        control.raise_if_shutdown()
        return PlanBuildResult[GeoHydrologyPlan](payload=GeoHydrologyPlan(
            coarse_surface_z=surface.surface_z, coarse_hydro=tuple(coarse), fine_z_overrides=delta,
            sparse_fine_hydro=tuple(((FineX(c[0]), FineY(c[1])), fine[c]) for c in sorted(fine, key=lambda c: (c[1], c[0]))),
            water_bodies=source.bodies, physical_unions=assembled.physical_unions,
            declared_paint=routes.base.declared_paint, source_mapping=source.source_mapping,
            classification_decisions=routes.classification_decisions), diagnostics=())
