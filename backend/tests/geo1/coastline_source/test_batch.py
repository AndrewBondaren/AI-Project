"""Captured coastline join feeds the existing shared lifecycle and spatial competition."""
from unittest import TestCase
from unittest.mock import patch

from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.generators.terrain.designedWater.strategies.authoredRegionStrategy import AuthoredRegionStrategy
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase, PlacementMode
from app.dataModel.placement.intent import PlacementIdentity
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.prepared import PreparedPlacementV2, PlacementCandidate, PlacementFootprint
from app.dataModel.placement.result import ResolvedPlacementV2, UnresolvedPlacementV2, DisabledPlacement
from app.dataModel.policy.policyEnums import PolicyDisableReason
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from tests.geo1.contracts.strategies.fixtures import draft_for
from tests.geo1.placement_policy.fixtures import bind, execute
from tests.geo1.coastline_source.fixtures import capture, prepare, intent


def start(value, *, others=()):
    request = value.geometry_request
    return PlacementSession.start(PlacementBatchV2(world_uid=request.pre_hydrology.ref.key.world_uid,
        snapshot_uid="pre-relief",snapshot_revision=request.pre_hydrology.ref.output_fingerprint,
        phase=PlacementPhase.PRE_RELIEF,topology=request.topology,
        objects=(value.admission,*others),accepted=()))


def geometry(value, input):
    # Procedural test drafts are supplied field facts: G6/G7 own real generators.
    draft = AuthoredRegionStrategy().design(input) if input.strategy is Strategy.AUTHORED_REGION else draft_for(input)
    return DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())


def submit(session,value,joined):
    result = geometry(value,joined)
    session.submit(PreparedPlacementV2(intent=intent(value.admission.header),original_area=result.original_area,
        candidates=result.candidates,decision=value.admission.decision))
    return result


class CoastlineSourceBatchTests(TestCase):
    def test_dry_auto_source_is_admitted_through_common_batch_without_future_water(self):
        value = capture()
        before = value.geometry_request.pre_hydrology.model_dump_json()
        session = start(value)
        self.assertEqual(session.ready_for_preparation(),(value.admission.header,))
        joined = prepare(value)
        submit(session,value,joined)
        outcome = session.step()
        self.assertIsInstance(outcome,ResolvedPlacementV2)
        self.assertEqual(outcome.identity.source_uid,value.source.location_uid)
        self.assertTrue(joined.constraints.required_cells <= outcome.footprint.cells)
        self.assertEqual(value.geometry_request.pre_hydrology.model_dump_json(),before)
        self.assertEqual(session.finish().results,(outcome,))

    def test_authored_zero_skips_adapter_and_geometry(self):
        with patch("app.application.worldData.generators.terrain.designedWater.preparation.coastlineWaterSourceAdapter.CoastlineConstraintPreparer.prepare",side_effect=AssertionError("geometry")):
            value = capture(priority=0)
            session = start(value)
            offered = session.ready_for_preparation()
            self.assertEqual(offered,())
            for _ in offered:
                submit(session,value,prepare(value))
            result = session.finish().results[0]
        self.assertIsInstance(result,DisabledPlacement)
        self.assertEqual(result.reason,PolicyDisableReason.ZERO_PRIORITY)

    def test_closed_authored_line_remains_valid_when_autoresolve_is_false(self):
        value = capture(strategy=Strategy.AUTHORED_REGION,closed=True,auto=False)
        session = start(value)
        session.ready_for_preparation()
        result = submit(session,value,prepare(value))
        self.assertIsInstance(session.step(),ResolvedPlacementV2)
        self.assertEqual(result.floor_z,-5)
        self.assertIsNone(result.floor_profile)

    def test_reserved_competitor_blocks_whole_coastline_without_moving_absolute_path(self):
        value = capture()
        joined = prepare(value)
        required = joined.constraints.required_cells
        source = CoastlineWaterSource(value=value.source.model_copy(update={"location_uid":"mountain","placement_specificity":9}))
        decision = execute(bind(source))
        header = PlacementHeader(identity=PlacementIdentity(world_uid="world",source_uid="mountain",region_uid="mountain-region"),
            mode=PlacementMode.ABSOLUTE,dependencies=(),permitted_overlaps=(),separations=())
        mountain = PlacementAdmissionInput(header=header,decision=decision)
        session = start(value,others=(mountain,))
        self.assertEqual(len(session.ready_for_preparation()),2)
        captured_path = joined.source.value.path
        submit(session,value,joined)
        session.submit(PreparedPlacementV2(intent=intent(header),original_area=1.0,
            candidates=(PlacementCandidate(candidate_uid="reserved-mountain",preference=0,
                footprint=PlacementFootprint(cells=frozenset({min(required)}),z_min=None,z_max=None)),),decision=mountain.decision))
        self.assertIsInstance(session.step(),ResolvedPlacementV2)
        outcome = session.step()
        self.assertIsInstance(outcome,UnresolvedPlacementV2)
        self.assertEqual(outcome.identity.source_uid,value.source.location_uid)
        self.assertEqual(joined.source.value.path,captured_path)
        self.assertEqual(outcome.prepared.candidates[0].footprint.cells,geometry(value,joined).candidates[0].footprint.cells)
