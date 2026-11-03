from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.preparation.capturedCompetitor import (
    start_native_placement_session, submit_captured_competitor,
)
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.placement.prepared import CapturedPlacementGeometry
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from tests.geo1.contracts.test_placement_lifecycle import batch, decision, member, prepared, variant
from tests.geo1.fine_water.test_fill import source
from tests.geo1.terrain_base.fixtures import Control


class CompetitorRosterTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = source(hills=False)[0]

    def setUp(self):
        self.parent = member("parent")
        self.water = member("water")
        ready_child = member("child", targets=("parent",))
        self.child = replace(ready_child, decision=replace(ready_child.decision, state=PolicyState.WAITING_SUPPORT,
                                                         waiting_supports=("parent",)))
        self.off = member("off", priority=0)
        self.failed = member("failed", chosen=decision().model_copy(update={"state": PolicyState.UNRESOLVED,
            "issues": (FieldPathError(("object",), "missing"),)}))
        self.batch = replace(batch(self.water, self.parent, self.off, self.child, self.failed),
            snapshot_revision=self.window.ref.output_fingerprint, topology=self.window.payload.topology)
        self.parent_record = self.capture(self.parent, ((1, 0),))
        self.child_record = self.capture(ready_child, ((2, 0),))
        self.records = (self.child_record, self.parent_record)

    def capture(self, obj, cells=((0, 0),)):
        geometry = prepared(obj, cells=cells)
        return CapturedPlacementGeometry(coordinate_space=CoordinateSpace.WORLD_FINE_GRID,
            pre_hydrology_ref=self.window.ref, intent=geometry.intent, original_area=geometry.original_area,
            candidates=geometry.candidates)

    def start(self, **changes):
        args = dict(batch=self.batch, water_intents=(prepared(self.water).intent,), before=self.window,
                    expected_before=self.window.ref, competitor_geometry=self.records,
                    reevaluate_support=lambda header, causes: decision(), control=Control())
        return start_native_placement_session(**(args | changes))

    def test_roster_survives_support_reevaluation_and_submission(self):
        session, roster = self.start()
        self.assertEqual(tuple(roster), ("child", "parent"))
        with self.assertRaises(TypeError):
            roster["extra"] = self.parent_record

        def prepare_ready(headers):
            for header in headers:
                uid = header.identity.region_uid
                if uid == "water":
                    session.submit(prepared(self.water))
                else:
                    record = roster[uid]
                    submit_captured_competitor(session=session, header=header, captured=record, before=self.window,
                        expected_before=self.window.ref, control=Control(),
                        prepare_competitor=lambda admission: prepared(admission, candidates=record.candidates))

        outcomes = {row.identity.region_uid: row.status for row in session.run(prepare_ready).results}
        self.assertEqual(outcomes, dict(parent="resolved", child="resolved", water="resolved",
                                        off="disabled", failed="unresolved"))

    def test_terminal_record_optional_but_still_validated(self):
        off = self.capture(member("off"))
        session, roster = self.start(competitor_geometry=(self.child_record, off, self.parent_record))
        self.assertEqual(roster["off"], off)
        self.assertNotIn(self.off.header, session.ready_for_preparation())
        stale = replace(off, pre_hydrology_ref=replace(self.window.ref,
            key=replace(self.window.ref.key, input_fingerprint=b"x" * 32)))
        with self.assertRaisesRegex(ValueError, "expected pre-water revision"):
            self.start(competitor_geometry=(self.child_record, stale, self.parent_record))

    def test_bad_roster_rejected_before_session_start(self):
        different_header = replace(self.child_record, intent=replace(self.child_record.intent, dependencies=()))
        outside = replace(self.child_record, candidates=(variant("outside", ((32, 0),)),))
        cases = (
            ("immutable tuple", list(self.records)),
            ("missing competitor geometry.*parent", (self.child_record,)),
            ("missing competitor geometry.*child", (self.parent_record,)),
            ("sorted unique", self.records[::-1]),
            ("sorted unique", (self.child_record, *self.records)),
            ("non-water batch header", (*self.records, self.capture(self.water))),
            ("non-water batch header", (*self.records, self.capture(member("unknown")))),
            ("placement header", (different_header, self.parent_record)),
            ("canonical fine coordinates", (outside, self.parent_record)),
        )
        with patch.object(PlacementSession, "start", side_effect=AssertionError("premature start")):
            for error, records in cases:
                with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                    self.start(competitor_geometry=records)
            with self.assertRaises(PlanBuildFailure):
                self.start(water_intents=(prepared(member("foreign")).intent,))

    def test_empty_roster_for_water_only(self):
        _, roster = self.start(batch=replace(self.batch, objects=(self.water,)), competitor_geometry=())
        self.assertFalse(roster)
