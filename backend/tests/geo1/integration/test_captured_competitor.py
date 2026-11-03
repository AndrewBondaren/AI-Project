from copy import replace
from unittest import TestCase
from unittest.mock import Mock

from app.application.worldData.generators.terrain.designedWater.preparation.capturedCompetitor import submit_captured_competitor
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.placement.common import AbsoluteMovement, PlacementPhase
from app.dataModel.placement.prepared import CapturedPlacementGeometry
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from tests.geo1.contracts.test_placement_lifecycle import batch, decision, member, prepared, variant
from tests.geo1.fine_water.test_fill import source
from tests.geo1.source_projection.test_projection import resign
from tests.geo1.terrain_base.fixtures import Control


class CapturedCompetitorTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = source(hills=False)[0]

    def setUp(self):
        self.obj = member("competitor")
        self.batch = replace(batch(self.obj), snapshot_revision=self.window.ref.output_fingerprint,
                             topology=self.window.payload.topology)
        self.session = PlacementSession.start(self.batch)
        self.header, = self.session.ready_for_preparation()
        self.prepared = prepared(self.obj)
        self.capture = CapturedPlacementGeometry(coordinate_space=CoordinateSpace.WORLD_FINE_GRID,
            pre_hydrology_ref=self.window.ref, intent=self.prepared.intent, original_area=self.prepared.original_area,
            candidates=self.prepared.candidates)
        self.callback = Mock(return_value=self.prepared)

    def submit(self, **changes):
        args = dict(session=self.session, header=self.header, captured=self.capture, before=self.window,
                    expected_before=self.window.ref, prepare_competitor=self.callback, control=Control())
        submit_captured_competitor(**(args | changes))

    def test_submit_uses_current_admission_and_common_queue(self):
        self.submit()
        self.callback.assert_called_once_with(self.session.objects["competitor"])
        self.session.step()
        outcome, = self.session.finish().results
        self.assertEqual(outcome.prepared, self.prepared)
        self.assertEqual(outcome.footprint, self.capture.candidates[0].footprint)

    def test_stale_plan_key_batch_and_header_fail_before_callback(self):
        stale = replace(self.window.ref, key=replace(self.window.ref.key, input_fingerprint=b"x" * 32))
        changed = replace(self.header, dependencies=member("competitor", targets=("other",)).header.dependencies)
        for message, changes in (
            ("expected pre-water revision", dict(captured=replace(self.capture, pre_hydrology_ref=stale))),
            ("expected pre-water revision", dict(expected_before=stale, captured=replace(self.capture, pre_hydrology_ref=stale))),
            ("pre-relief frame", dict(session=PlacementSession.start(replace(self.batch, snapshot_revision=b"x" * 32)))),
            ("pre-relief frame", dict(session=PlacementSession.start(replace(self.batch, phase=PlacementPhase.DEPENDENT)))),
            ("pre-relief frame", dict(session=PlacementSession.start(replace(self.batch, topology=batch().topology)))),
            ("offered ready header", dict(session=PlacementSession.start(self.batch))),
            ("offered placement header", dict(header=changed)),
            ("offered placement header", dict(captured=replace(self.capture,
                intent=replace(self.capture.intent, dependencies=changed.dependencies)))),
        ):
            with self.subTest(fields=tuple(changes)), self.assertRaisesRegex(ValueError, message):
                self.submit(**changes)
        self.callback.assert_not_called()
        self.submit()

    def test_all_candidates_checked_without_wrapping_into_frame(self):
        for mode in (WorldTopologyMode.PLANAR, WorldTopologyMode.WRAPPED, WorldTopologyMode.SPHERE):
            window = resign(self.window, payload=replace(self.window.payload,
                topology=replace(self.window.payload.topology, mode=mode)))
            session = PlacementSession.start(replace(self.batch, topology=window.payload.topology,
                snapshot_revision=window.ref.output_fingerprint))
            session.ready_for_preparation()
            capture = replace(self.capture, pre_hydrology_ref=window.ref,
                intent=replace(self.capture.intent, absolute_movement=AbsoluteMovement.EXPLICIT_CANDIDATES),
                candidates=(*self.capture.candidates, variant("outside", ((32, 0),))))
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "canonical fine coordinates"):
                self.submit(session=session, before=window, expected_before=window.ref, captured=capture)
            self.assertEqual(session.offered, {"competitor"})
        self.callback.assert_not_called()

    def test_callback_cannot_change_geometry_or_decision_and_retry_succeeds(self):
        for changes in (dict(original_area=2), dict(candidates=(variant("new", ((0, 1),)),)),
                        dict(intent=replace(self.prepared.intent, placement_specificity=9)),
                        dict(decision=decision(priority=8))):
            callback = Mock(return_value=replace(self.prepared, **changes))
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                self.submit(prepare_competitor=callback)
            self.assertEqual(self.session.offered, {"competitor"})
            self.assertFalse(self.session.queue.prepared)
        self.submit()

    def test_cancel_after_preparation_allows_retry(self):
        control = Mock()
        def cancel(admission):
            control.raise_if_shutdown.side_effect = InterruptedError()
            return self.prepared
        with self.assertRaises(InterruptedError):
            self.submit(prepare_competitor=cancel, control=control)
        self.assertFalse(self.session.queue.prepared)
        self.submit()
