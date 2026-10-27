"""G0-P isolated admission: no geometry for non-created objects, one shared queue."""

from itertools import permutations
from enum import StrEnum
from unittest import TestCase

from pydantic import ValidationError

from app.application.policy.policyResolver import PolicyResolver
from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.placement.diagnostics import emit_diagnostics
from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.intent import PlacementDependency, PlacementIdentity, PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import (
    DisabledPlacement, PlacementBatchResultV2, PlacementIssueCode, ResolvedPlacementV2, UnresolvedPlacementV2,
)
from app.dataModel.policy.policyEnums import PolicyDisableReason, PolicyStage, PolicyState, PolicySupportState, PolicyRuleId, RulePrecedence
from app.dataModel.policy.policyBindings import PolicyInputs
from app.dataModel.policy.policyRules import Equal, PolicyRule, RequireSupportEffect, SelectPriorityDefaultEffect
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.contracts.test_policy_resolver import (
    Action, FLAG, TERMINAL, Settings, Defaults, admission, sources, facts, rule, support,
)
from test_placement_resolver import SNAPSHOT_REVISION, topology, variant


def decision(priority=1):
    return PolicyResolver().resolve(admission(), sources(Settings(priority=priority)), facts(),
                                    mode=ResolutionMode.VALIDATE_ONLY)


def member(uid, *, priority=1, chosen=None, targets=()):
    intent = PlacementIntent(identity=PlacementIdentity(world_uid="world", source_uid=f"source-{uid}", region_uid=uid),
        mode="absolute", shape=None, dependencies=tuple(PlacementDependency(target_uid=t, relation="resolved") for t in targets),
        permitted_overlaps=(), separations=())
    return PlacementAdmissionInput(header=PlacementHeader.from_intent(intent), decision=chosen or decision(priority))


def prepared(obj, *, cells=((0, 0),), area=1.0, candidates=None):
    h = obj.header
    intent = PlacementIntent(identity=h.identity, mode=h.mode, shape=None, dependencies=h.dependencies,
                             permitted_overlaps=h.permitted_overlaps, separations=h.separations)
    return PreparedPlacementV2(intent=intent, original_area=area, decision=obj.decision,
        candidates=(variant(h.identity.region_uid + "/candidate", cells),) if candidates is None else candidates)


def batch(*objects, accepted=(), phase="pre_relief"):
    return PlacementBatchV2(world_uid="world", snapshot_uid="snapshot", snapshot_revision=SNAPSHOT_REVISION,
        phase=phase, topology=topology(), objects=objects, accepted=accepted)


def drive(session, *, cells=None, areas=None):
    while session.queue.pending:
        portion = session.ready_for_preparation()
        for header in portion:
            uid = header.identity.region_uid
            session.submit(prepared(session.objects[uid], cells=(cells or {}).get(uid, ((0, 0),)),
                                    area=(areas or {}).get(uid, 1.0)))
        if session.step() is None:
            break
    return session.finish()


class PlacementLifecycleTests(TestCase):
    def test_zero_objects_from_different_domains_never_request_preparation(self):
        for uid in ("water", "mountain", "other"):
            with self.subTest(uid=uid):
                obj = member(uid, priority=0, targets=("missing",))
                session = PlacementSession.start(batch(obj))
                self.assertEqual(session.ready_for_preparation(), ())
                result = session.finish()
                disabled = result.results[0]
                self.assertIsInstance(disabled, DisabledPlacement)
                self.assertEqual(disabled.reason, PolicyDisableReason.ZERO_PRIORITY)
                self.assertFalse(result.diagnostics)
                self.assertFalse(session.placed)
                self.assertFalse(session.queue.prepared)

    def test_authored_and_effective_zero_are_both_normal_disabled(self):
        implicit = PolicyResolver().resolve(admission(), sources(Settings(), Defaults(priority=0)), facts(),
                                            mode=ResolutionMode.VALIDATE_ONLY)
        for chosen in (decision(0), implicit):
            result = PlacementSession.start(batch(member("off", chosen=chosen))).finish()
            self.assertIsInstance(result.results[0], DisabledPlacement)
            self.assertFalse(result.diagnostics)

    def test_disabled_parent_does_not_give_child_false_support(self):
        for objects in permutations((member("off", priority=0), member("child", targets=("off",)), member("free"))):
            result = drive(PlacementSession.start(batch(*objects)))
            outcomes = {r.identity.region_uid: r for r in result.results}
            self.assertIsInstance(outcomes["free"], ResolvedPlacementV2)
            self.assertEqual(outcomes["child"].reason, PolicyDisableReason.SUPPORT_DISABLED)
            self.assertEqual(outcomes["child"].causes[0].region_uid, "off")

    def test_failed_parent_dominates_another_disabled_parent(self):
        session = PlacementSession.start(batch(member("off", priority=0),
            member("failed", targets=("missing",)), member("child", targets=("off", "failed"))))
        result = session.finish()
        child = next(r for r in result.results if r.identity.region_uid == "child")
        self.assertIsInstance(child, UnresolvedPlacementV2)
        self.assertEqual({r.region_uid for r in child.causes}, {"off", "failed"})
        self.assertEqual(child.diagnostics[0].code, PlacementIssueCode.FAILED_DEPENDENCY)

    def test_cycles_fail_without_stalling_independent_placement(self):
        result = drive(PlacementSession.start(batch(member("a", targets=("b",)), member("b", targets=("a",)),
                                                     member("downstream", targets=("a",)), member("free"))))
        outcomes = {r.identity.region_uid: r for r in result.results}
        self.assertIsInstance(outcomes["free"], ResolvedPlacementV2)
        for uid in ("a", "b"):
            self.assertEqual(outcomes[uid].diagnostics[0].code, PlacementIssueCode.DEPENDENCY_CYCLE)
        self.assertEqual(outcomes["downstream"].diagnostics[0].code, PlacementIssueCode.FAILED_DEPENDENCY)

    def test_disabled_cycle_member_does_not_wait_for_the_cycle(self):
        result = PlacementSession.start(batch(member("a", priority=0, targets=("b",)),
                                              member("b", targets=("a",)))).finish()
        self.assertTrue(all(isinstance(r, DisabledPlacement) for r in result.results))

    def test_all_newly_ready_children_submit_before_next_heap_winner(self):
        parent = member("parent", priority=5)
        child = member("child", priority=20, targets=("parent",))
        competitor = member("competitor", priority=2)
        session = PlacementSession.start(batch(parent, child, competitor))
        self.assertEqual({h.identity.region_uid for h in session.ready_for_preparation()}, {"parent", "competitor"})
        session.submit(prepared(parent, cells=((2, 0),)))
        session.submit(prepared(competitor))
        self.assertEqual(session.step().identity.region_uid, "parent")
        with self.assertRaises(ValueError):
            session.step()
        session.submit(prepared(child))
        self.assertEqual(session.step().identity.region_uid, "child")
        self.assertIsInstance(session.step(), UnresolvedPlacementV2)

    def test_priority_area_uid_order_is_stable_for_positive_candidates(self):
        for ordering in permutations((member("a", priority=2), member("b", priority=2), member("c", priority=1))):
            result = drive(PlacementSession.start(batch(*ordering)), areas={"a": 1.0, "b": 3.0})
            winners = [r.identity.region_uid for r in result.results if isinstance(r, ResolvedPlacementV2)]
            self.assertEqual(winners, ["b"])

    def test_incomplete_portion_cannot_advance_heap(self):
        a, b = member("a"), member("b")
        session = PlacementSession.start(batch(a, b))
        session.ready_for_preparation()
        session.submit(prepared(a))
        with self.assertRaises(ValueError):
            session.step()
        session.submit(prepared(b, cells=((2, 0),)))
        self.assertIsNotNone(session.step())

    def test_prepared_contract_rejects_disabled_or_nonpositive_decision(self):
        with self.assertRaises(ValidationError):
            prepared(member("off", priority=0))
        forged = decision().model_copy(update={"effective_priority": 0})
        with self.assertRaises(ValidationError):
            prepared(member("forged", chosen=forged))

    def test_submit_must_match_header_and_decision(self):
        obj = member("a")
        session = PlacementSession.start(batch(obj))
        session.ready_for_preparation()
        for other in (member("wrong"), member("a", priority=3)):
            with self.assertRaises(ValueError):
                session.submit(prepared(other))
        session.submit(prepared(obj))
        with self.assertRaises(ValueError):
            session.submit(prepared(obj))

    def test_unresolved_before_geometry_and_missing_priority_are_explicit(self):
        missing = PolicyResolver().resolve(admission(), PolicyInputs(), facts(),
                                          mode=ResolutionMode.VALIDATE_ONLY)
        result = PlacementSession.start(batch(member("missing", chosen=missing))).finish()
        self.assertIsInstance(result.results[0], UnresolvedPlacementV2)
        self.assertIsNone(result.results[0].prepared)
        self.assertTrue(result.diagnostics)

    def test_empty_candidates_and_outside_topology_are_spatial_failures(self):
        for variants in ((), (variant("outside", ((999, 0),)),)):
            obj = member("a")
            session = PlacementSession.start(batch(obj))
            session.ready_for_preparation()
            session.submit(prepared(obj, candidates=variants))
            self.assertIsInstance(session.step(), UnresolvedPlacementV2)

    def test_support_resume_preserves_priority_and_only_runs_for_new_facts(self):
        spec = admission((rule(stage=PolicyStage.SUPPORT, effect=RequireSupportEffect(("parent",))),))
        inputs = sources(Settings(priority=8))
        waiting = PolicyResolver().resolve(spec, inputs, facts(supports=(support("parent", PolicySupportState.PENDING),)),
                                           mode=ResolutionMode.VALIDATE_ONLY)
        parent = member("parent")
        child = member("child", chosen=waiting, targets=("parent",))
        calls = []
        def resume(header, refs):
            calls.append(refs)
            return PolicyResolver().resolve(spec, inputs, facts(supports=(support("parent", PolicySupportState.ACCEPTED),)),
                                            mode=ResolutionMode.VALIDATE_ONLY, resume=waiting)
        session = PlacementSession.start(batch(parent, child), reevaluate_support=resume)
        session.ready_for_preparation()
        session.submit(prepared(parent, cells=((2, 0),)))
        session.step()
        session.ready_for_preparation()
        session.ready_for_preparation()
        self.assertEqual(len(calls), 1)
        self.assertEqual(session.objects["child"].decision.effective_priority, 8)
        session.submit(prepared(session.objects["child"]))
        self.assertIsInstance(session.step(), ResolvedPlacementV2)

    def test_resume_callback_cannot_change_priority(self):
        waiting = decision(2).model_copy(update={"state": PolicyState.WAITING_SUPPORT, "waiting_supports": ("p",)})
        child = member("child", chosen=waiting, targets=("p",))
        session = PlacementSession.start(batch(member("p"), child), reevaluate_support=lambda h, r: decision(3))
        session.ready_for_preparation()
        session.submit(prepared(session.objects["p"]))
        with self.assertRaises(ValueError):
            session.step()

    def test_finish_unprepared_members_and_waiters_are_terminal(self):
        result = PlacementSession.start(batch(member("unprepared"))).finish()
        self.assertIsInstance(result.results[0], UnresolvedPlacementV2)
        waiting = decision(2).model_copy(update={"state": PolicyState.WAITING_SUPPORT, "waiting_supports": ("p",)})
        result = drive(PlacementSession.start(batch(member("p"), member("c", chosen=waiting, targets=("p",)))))
        self.assertTrue(all(r.status in ("resolved", "unresolved", "disabled") for r in result.results))

    def test_batch_validates_all_three_outcome_identities(self):
        session = PlacementSession.start(batch(member("off", priority=0)))
        result = session.finish()
        with self.assertRaises(ValidationError):
            PlacementBatchResultV2.model_validate(result.model_copy(update={"results": result.results * 2}))
        with self.assertRaises(ValidationError):
            PlacementBatchResultV2.model_validate(result.model_copy(update={"world_uid": "another"}))

    def test_accepted_and_authored_inputs_remain_unchanged(self):
        first = drive(PlacementSession.start(batch(member("accepted"))))
        accepted = first.results[0]
        before = accepted.model_dump()
        obj = member("child")
        drive(PlacementSession.start(batch(obj, accepted=(accepted,), phase="dependent")))
        self.assertEqual(accepted.model_dump(), before)
        self.assertIsNone(obj.header.model_dump().get("placement_specificity"))

    def test_domain_default_is_read_from_actual_bound_pojo(self):
        for default in (0, 2):
            selected = PolicyResolver().resolve(admission(), sources(Settings(), Defaults(priority=default)), facts(),
                                                mode=ResolutionMode.VALIDATE_ONLY)
            result = drive(PlacementSession.start(batch(member("body", chosen=selected))))
            self.assertIsInstance(result.results[0], DisabledPlacement if default == 0 else ResolvedPlacementV2)

    def test_missing_dependency_keeps_later_disabled_cause(self):
        session = PlacementSession.start(batch(member("root", priority=0), member("off", targets=("root",)),
            member("child", targets=("missing", "off"))))
        child = next(r for r in session.finish().results if r.identity.region_uid == "child")
        self.assertIsInstance(child, UnresolvedPlacementV2)
        self.assertEqual({r.region_uid: r.status.value for r in child.causes}, {"missing": "unresolved", "off": "disabled"})

    def test_dry_coastline_is_policy_disabled_with_domain_reason(self):
        class DryReason(StrEnum):
            DRY_TARGET = "dry_target"
        dry = PolicyRule[Action, DryReason](id=PolicyRuleId("dry"), stage=PolicyStage.PRIORITY,
            precedence=RulePrecedence(1), conditions=(Equal(FLAG, False),),
            effect=SelectPriorityDefaultEffect(TERMINAL), domain_reason=DryReason.DRY_TARGET)
        selected = PolicyResolver().resolve(admission((dry,)), sources(Settings()), facts(False),
                                            mode=ResolutionMode.VALIDATE_ONLY)
        result = PlacementSession.start(batch(member("coastline", chosen=selected))).finish()
        self.assertIsInstance(result.results[0], DisabledPlacement)
        self.assertIn(DryReason.DRY_TARGET, [r.domain_reason for r in result.results[0].decision.reasons])
        ctx = ResolveContext(validate_only=True)
        emit_diagnostics(result, ctx)
        self.assertFalse(ctx.errors)
