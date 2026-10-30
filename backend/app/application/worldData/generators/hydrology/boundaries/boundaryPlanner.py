"""Public boundary operation; domain jobs own preparation and result semantics."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.boundaries.boundaryPreparation import BoundaryPreparationJob
from app.application.worldData.generators.hydrology.boundaries.boundaryResult import BoundaryResultAssembler
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput, CoastlineBoundaryPlan
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader


class CoastlineBoundaryPlanner:
    """Coordinate one boundary operation through stable domain and placement APIs."""

    def prepare[H: HydrologyPlan](self, input: CoastlineBoundaryInput, snapshot: BoundaryWaterSnapshot[H],
                admissions: tuple[PlacementAdmissionInput, ...], *, snapshot_uid: EntityUid) -> CoastlineBoundaryPlan:
        preparation = BoundaryPreparationJob(input, snapshot, admissions, snapshot_uid=snapshot_uid)
        results = BoundaryResultAssembler(preparation.input, preparation.snapshot, preparation.batch)
        session = PlacementSession.start(preparation.batch)

        def prepare_ready(headers: tuple[PlacementHeader, ...]) -> None:
            for header in headers:
                try:
                    result = preparation.prepare(session.objects[header.identity.region_uid])
                    results.record(result.boundary)
                    session.submit(result.prepared)
                except PlanBuildFailure as failure:
                    session.fail(header.identity, results.record_failure(header, failure.issues))

        return results.assemble(session.run(prepare_ready))
