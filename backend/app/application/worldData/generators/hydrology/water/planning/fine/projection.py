"""Canonical water projection and captured physical-input closure, never refill."""
from bisect import bisect_left, bisect_right

from app.application.planning.service.planFingerprints import input_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.coordinates.light.grid import light_cell_center_fine
from app.application.worldData.generators.hydrology.water.planning.fine.publication import (
    FINE_WATER_CONTRACT, FineWaterPublicationJob,
)
from app.application.worldData.generators.hydrology.water.planning.geoExecution import geo_execution_decisions
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult, OpenWaterPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY, SurfaceGridCoord
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class FineWaterProjectionJob:
    def project(self, water: PlanEnvelope[FineWaterResult], *, expected_water: PlanRef,
                world_uid: EntityUid, inputs: GeoHydrologyPlanInput, specs: tuple[BasinSpec, ...],
                classification_decisions: tuple[tuple[Category, HydrologyGenerationDecision], ...],
                control: PlanBuildControl) -> PlanBuildResult[OpenWaterPlan]:
        water = FineWaterPublicationJob.admit_result(water, expected_water=expected_water,
            world_uid=world_uid, inputs=inputs, control=control)
        decisions = geo_execution_decisions(classification_decisions)
        expected = input_fingerprint(FINE_WATER_CONTRACT, world_uid, water.ref.key.scope,
            (inputs, tuple(sorted(specs, key=lambda spec: spec.source_uid)), decisions),
            water.dependencies, SURFACE_MANIFEST)
        if expected != water.ref.key.input_fingerprint:
            raise ValueError("projection inputs/specs/decisions must match the exact fine-water operation")
        window, assembled = water.payload
        rows, spans = assembled.materialized.cells, window.coverage.spans
        scale, bounds = LightGridScale.from_tile(inputs.grid.fine_span, 1), inputs.topology.bounds
        projected = []
        for gy in range(bounds.y_min, bounds.y_max+1):
            control.raise_if_shutdown()
            for gx in range(bounds.x_min, bounds.x_max+1):
                x, y = light_cell_center_fine(gx, gy, 0, 0, scale)
                i = bisect_right(spans, (y, x), key=lambda span: (span.y, span.x0))-1
                if i < 0 or spans[i].y != y or x >= spans[i].x1:
                    raise PlanBuildFailure((FieldPathError(("projection", gx, gy), "missing fine water observation"),))
                i = bisect_left(rows, (y, x), key=lambda row: (row[0][1], row[0][0]))
                if i < len(rows) and rows[i][0] == (x, y):
                    projected.append((SurfaceGridCoord(GridX(gx), GridY(gy)), rows[i][1]))
        control.raise_if_shutdown()
        return PlanBuildResult[OpenWaterPlan](payload=OpenWaterPlan(coarse_open_water=tuple(projected),
            water_bodies=assembled.materialized.bodies, physical_unions=assembled.physical_unions,
            source_mapping=assembled.materialized.source_mapping), diagnostics=water.diagnostics)
