"""Post-fill caller uses common dependent lifecycle; errors do not stop independent boundaries."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometry
from app.application.worldData.generators.hydrology.boundaries.boundaryPlanner import CoastlineBoundaryPlanner
from app.dataModel.hydrology.boundaries.attachedCoastline import AttachedCoastline, BoundaryIssueCode
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.placement.result import ResolvedPlacementV2, UnresolvedPlacementV2, DisabledPlacement
from app.dataModel.placement.lifecycle.causal import PlacementOutcomeStatus
from app.dataModel.policy.policyEnums import PolicySupportState, PolicyDisableReason
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.boundaries.fixtures import make


def plan(case):
    return CoastlineBoundaryPlanner().prepare(case.input,case.snapshot,(case.admission,),snapshot_uid="dependent-snapshot")


class BoundaryPlannerTests(TestCase):
    def test_valid_boundary_resolves_with_immutable_accepted_supports(self):
        case=make()
        before=case.snapshot.model_dump_json()
        result=plan(case)
        self.assertEqual(len(result.boundaries),1)
        self.assertIsInstance(result.outcomes[0],ResolvedPlacementV2)
        self.assertFalse(result.issues)
        self.assertEqual(case.snapshot.model_dump_json(),before)
        boundary=result.boundaries[0]
        self.assertEqual(AttachedCoastline.model_validate_json(boundary.model_dump_json()),boundary)

    def test_zero_and_dry_targets_skip_geometry(self):
        for case in (make(priority=0),make(dry=True)):
            with patch.object(BoundaryGeometry,"prepare",side_effect=AssertionError("geometry")):
                result=plan(case)
            self.assertFalse(result.boundaries)
            self.assertIsInstance(result.outcomes[0],DisabledPlacement)

    def test_nonaccepted_supports_preserve_common_state_and_actual_causes(self):
        for support in (PolicySupportState.DISABLED,PolicySupportState.MISSING,PolicySupportState.FAILED,None):
            case=make(support=support)
            with patch.object(BoundaryGeometry,"prepare",side_effect=AssertionError("geometry")):
                result=plan(case)
            self.assertFalse(result.boundaries)
            if support is PolicySupportState.DISABLED:
                self.assertIsInstance(result.outcomes[0],DisabledPlacement)
                self.assertEqual(result.outcomes[0].reason,PolicyDisableReason.SUPPORT_DISABLED)
                self.assertEqual(result.outcomes[0].causes[0].region_uid,"water-region")
                self.assertEqual(result.outcomes[0].causes[0].status,PlacementOutcomeStatus.DISABLED)
            else:
                self.assertIsInstance(result.outcomes[0],UnresolvedPlacementV2)
                if support is PolicySupportState.FAILED:
                    self.assertEqual(result.outcomes[0].causes[0].region_uid,"water-region")
                    self.assertEqual(result.outcomes[0].causes[0].status,PlacementOutcomeStatus.UNRESOLVED)

    def test_off_target_and_unknown_fine_errors_preserve_original_issue_code(self):
        base=make()
        off=base.source.model_copy(update={"path":tuple(point.model_copy(update={"x":0}) for point in base.source.path)})
        for case,code in ((make(source=off),BoundaryIssueCode.BOUNDARY_OFF_TARGET),
                          (make(missing_samples=((1,2),)),BoundaryIssueCode.UNKNOWN_FINE_WATER)):
            result=plan(case)
            self.assertFalse(result.boundaries)
            self.assertIsInstance(result.outcomes[0],UnresolvedPlacementV2)
            self.assertEqual(result.issues[0].code,code.value)
            self.assertTrue(result.outcomes[0].diagnostics)
            issue = result.issues[0]
            diagnostic = result.outcomes[0].diagnostics[0]
            self.assertEqual(diagnostic.detail, issue.message)
            self.assertEqual(diagnostic.path[-len(issue.path):], issue.path)

    def test_own_zero_disable_is_not_attributed_to_failed_or_disabled_water(self):
        for support in (PolicySupportState.FAILED, PolicySupportState.DISABLED):
            with self.subTest(support=support):
                case = make(priority=0, support=support)
                result = plan(case)
                outcome = result.outcomes[0]
                self.assertIsInstance(outcome, DisabledPlacement)
                self.assertEqual(outcome.reason, PolicyDisableReason.ZERO_PRIORITY)
                self.assertEqual(outcome.causes, ())
                self.assertEqual(outcome.decision, case.admission.decision)
                self.assertFalse(result.boundaries)

    def test_target_cause_uses_actual_placement_region_without_changing_decision(self):
        case = make(support=PolicySupportState.DISABLED)
        target = case.snapshot.water_outcomes[0]
        target = target.model_copy(update={"identity": target.identity.model_copy(update={
            "region_uid": "actual-target-region"})})
        snapshot = case.snapshot.model_copy(update={"water_outcomes": (target,)})
        result = plan(replace(case, snapshot=snapshot))
        outcome = result.outcomes[0]
        self.assertEqual(outcome.reason, PolicyDisableReason.SUPPORT_DISABLED)
        self.assertEqual(tuple((cause.region_uid, cause.status) for cause in outcome.causes),
                         (("actual-target-region", PlacementOutcomeStatus.DISABLED),))
        self.assertEqual(outcome.decision, case.admission.decision)
        self.assertEqual(snapshot.water_outcomes, (target,))

    def test_merged_sources_use_explicit_shared_boundary_rules(self):
        result=plan(make(merged=True))
        self.assertEqual(len(result.boundaries),1)
        self.assertEqual(result.boundaries[0].parts[0].body_uid,"body-a")

    def test_split_physical_bodies_emit_one_boundary_with_separate_parts(self):
        result=plan(make(split=True))
        self.assertEqual(len(result.boundaries),1)
        self.assertEqual({part.body_uid for part in result.boundaries[0].parts},{"body-a","body-b"})

    def test_independent_valid_boundary_continues_after_bad_geometry(self):
        good=make()
        bad_source=good.source.model_copy(update={"location_uid":"bad-boundary",
            "path":(HydrologyWaypoint(x=0,y=1),HydrologyWaypoint(x=0,y=4))})
        bad=make(source=bad_source)
        header=bad.admission.header.model_copy(update={"identity":bad.admission.header.identity.model_copy(update={"region_uid":"bad-region"})})
        bad_admission=bad.admission.model_copy(update={"header":header})
        input=good.input.model_copy(update={"sources":(good.source,bad_source)})
        result=CoastlineBoundaryPlanner().prepare(input,good.snapshot,(good.admission,bad_admission),snapshot_uid="dependent-snapshot")
        self.assertEqual(tuple(boundary.source_uid for boundary in result.boundaries),("boundary",))
        self.assertEqual(len(result.outcomes),2)
        self.assertEqual(len(result.issues),1)

    def test_no_policy_execution_or_requested_tiles_in_caller(self):
        case=make()
        with patch.object(PolicyResolver,"resolve",side_effect=AssertionError("policy")):
            result=plan(case)
        self.assertEqual(result,plan(case))
        self.assertEqual(plan(make()),plan(make(resolution=ResolutionMode.RUNTIME)))
        self.assertNotIn("requested_tiles",type(case.input).model_fields)

    def test_scope_and_admission_mismatches_are_explicit(self):
        case=make()
        with self.assertRaises(PlanBuildFailure):
            CoastlineBoundaryPlanner().prepare(case.input,case.snapshot,(),snapshot_uid="dependent-snapshot")
        with self.assertRaises(PlanBuildFailure):
            plan(replace(case,input=case.input.model_copy(update={"grid":case.input.grid.model_copy(update={"fine_span":1})})))
        with self.assertRaises(ValidationError):
            type(case.input).model_validate(case.input.model_copy(update={"sources":case.input.sources*2}))
