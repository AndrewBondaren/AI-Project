"""Revision-scoped readonly native water observations; admission is outside reads."""
from bisect import bisect_left, bisect_right

from app.application.planning.service.planFingerprints import output_fingerprint
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.planning.assembly.final.publication import NATIVE_FINAL, ROUTES, RIVER
from app.application.worldData.generators.hydrology.rivers.planning.fine.publication import FINE_WATER
from app.application.worldData.generators.hydrology.water.planning.fine.publication import FINE_WATER_CONTRACT, PRE_WATER_SURFACE
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.policy.policyFacts import KnownFact, UnknownFact
from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class NativeFinalWaterQuery:
    def __init__(self, final: PlanEnvelope[GeoHydrologyPlan], water: PlanEnvelope[FineWaterResult], *,
                 expected_final: PlanRef, expected_water: PlanRef, control: PlanBuildControl) -> None:
        control.raise_if_shutdown()
        final = PlanEnvelope[GeoHydrologyPlan].model_validate(final)
        water = PlanEnvelope[FineWaterResult].model_validate(water)
        for envelope, expected, contract in ((final, expected_final, NATIVE_FINAL),
                                             (water, expected_water, FINE_WATER_CONTRACT)):
            key = envelope.ref.key
            if (envelope.ref != expected or key.world_uid != expected_final.key.world_uid
                    or key.scope != expected_final.key.scope
                    or (key.contract_id, key.schema_version, key.algorithm_version)
                    != (contract.id, contract.schema_version, contract.algorithm_version)
                    or envelope.ref.output_fingerprint != output_fingerprint(
                        envelope.payload, envelope.dependencies, envelope.diagnostics, SURFACE_MANIFEST)):
                raise ValueError("water query requires exact native final/source revisions and output proofs")
        refs = {d.slot: d.ref for d in final.dependencies}
        source_refs = {d.slot: d.ref for d in water.dependencies}
        if (set(refs) != {FINE_WATER, PRE_WATER_SURFACE, ROUTES, RIVER}
                or any(ref.key.world_uid != final.ref.key.world_uid or ref.key.scope != final.ref.key.scope
                       for ref in refs.values())
                or refs.get(FINE_WATER) != water.ref or refs.get(PRE_WATER_SURFACE) is None
                or refs.get(PRE_WATER_SURFACE) != source_refs.get(PRE_WATER_SURFACE)):
            raise ValueError("water query requires final's exact successful source dependency")
        errors = tuple(d.issue for d in water.diagnostics if d.disposition is PlanDiagnosticDisposition.ERROR)
        if errors:
            raise PlanBuildFailure(errors)
        self._coverage = water.payload[0].coverage.spans
        self._rows = final.payload.sparse_fine_hydro
        # Admit geometry once; absent final facts imply dry only inside this source's observations.
        for cell, fact in self._rows:
            control.raise_if_shutdown()
            if not self._observed(cell):
                raise ValueError("final water facts outside source observations")
            if (fact.liquid_candidate or fact.role is HydrologyCellRole.RIVER_BED) and fact.water_body_uid is None:
                raise ValueError("observed water requires its actual identity")
        control.raise_if_shutdown()

    def _observed(self, cell: FineXY) -> bool:
        x, y = cell
        i = bisect_right(self._coverage, (y, x), key=lambda span: (span.y, span.x0))-1
        return i >= 0 and self._coverage[i].y == y and x < self._coverage[i].x1

    def water_at(self, cell: FineXY) -> KnownFact[EntityUid | None] | UnknownFact:
        if not self._observed(cell):
            return UnknownFact(issue=FieldPathError(("hydrology", "coverage", *cell), "fine water observation is unknown"))
        i = bisect_left(self._rows, (cell[1], cell[0]), key=lambda row: (row[0][1], row[0][0]))
        if i < len(self._rows) and self._rows[i][0] == cell:
            fact = self._rows[i][1]
            if fact.liquid_candidate or fact.role is HydrologyCellRole.RIVER_BED:
                return KnownFact[EntityUid | None](value=fact.water_body_uid)
        return KnownFact[EntityUid | None](value=None)
