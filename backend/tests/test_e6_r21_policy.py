"""R21 errors reach the common sink without alternative terrain/template/canal."""
import unittest
from unittest.mock import patch

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.worldData.generators.terrain.relief.pick.templatePick import PickResult, pick_template, resolve_picked_template
from app.application.worldData.generators.terrain.relief.canal.attachments import resolve_knobs_canal
from app.application.worldData.generators.terrain.relief.canal.obstacleResolve import resolve_canal_obstacle_cut
from app.application.worldData.generators.terrain.relief.canal.seedResolve import resolve_seed_canal
from app.dataModel.terrain.relief.canalObstaclePolicy import CanalObstaclePolicyRule
from app.dataModel.terrain.relief.enums import CanalObstacleEntity, ReliefPickMode
from app.dataModel.terrain.relief.worldCanalTemplateRegistry import WorldCanalTemplateRegistry
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy, ReliefContextPickPolicy
from app.dataModel.terrain.relief.worldReliefTemplateRegistry import WorldReliefTemplateRegistry
from app.dataModel.terrain.relief import ReliefTemplate
from app.application.worldData.generators.terrain.relief.pick.gradePass import grade_from_template
from app.application.worldData.generators.terrain.relief.pick.gradeConstrained import grade_constrained


class R21PolicyTests(unittest.TestCase):
    def assert_policy_error(self, operation, code):
        facts = []
        for preview in (False, True):
            ctx = ResolveContext.for_import(validate_only=preview)
            with patch("app.application.jsonValidation.resolve.logger") as log:
                with self.assertRaises(UnresolvedModelError) as caught:
                    operation(ctx)
            facts.append(caught.exception.issues)
            self.assertEqual(log.warning.call_count, 0 if preview else 1)
            self.assertEqual(facts[-1][0].code, code)
            self.assertEqual(ctx.errors, facts[-1])
        self.assertEqual(facts[0], facts[1])

    def test_empty_candidates_and_missing_fixed_do_not_pick_alternatives(self):
        policy = WorldReliefPickPolicy()
        registry = WorldReliefTemplateRegistry([])
        def pick(ctx):
            return pick_template(context="mountain", registry=registry, world_policy=policy,
                world_seed="seed", site_id="site", resolve_ctx=ctx)
        self.assert_policy_error(pick, "DOMAIN_NO_CANDIDATE")
        registry = WorldReliefTemplateRegistry.model_validate([{"context": "mountain", "system_template_uid": "other"}])
        policy = WorldReliefPickPolicy(mountain=ReliefContextPickPolicy(mode="fixed", default_template_uid="missing"))
        self.assert_policy_error(pick, "REF_W_UNKNOWN")

    def test_required_body_cannot_turn_into_skip(self):
        pick = PickResult("missing", "world", ReliefPickMode.FIXED, "fixed")
        self.assert_policy_error(lambda ctx: resolve_picked_template(pick, {}, resolve_ctx=ctx), "REF_W_UNAVAILABLE")

    def test_unknown_canals_reject_both_resolve_paths(self):
        registry = WorldCanalTemplateRegistry.canonical_defaults()
        self.assert_policy_error(lambda ctx: resolve_knobs_canal(earthen_canal=None,
            structure_canal="missing", structure_refs=(), registry=registry, resolve_ctx=ctx), "REF_W_UNKNOWN")
        self.assert_policy_error(lambda ctx: resolve_seed_canal(requested_length=2, L_eff=2,
            terrain_key="plains", knobs_earthen=None, knobs_structure_canal="missing",
            policy_rules=[], registry=registry, site_id="site", resolve_ctx=ctx), "REF_W_UNKNOWN")

    def test_conflicting_enabled_rules_do_not_disable_cut(self):
        rules = [CanalObstaclePolicyRule(to_canal_cut_enable=True, entities=["all"], canal_ref=ref)
                 for ref in ("one", "two")]
        self.assert_policy_error(lambda ctx: resolve_canal_obstacle_cut(entity=CanalObstacleEntity.PLAINS,
            rules=rules, resolve_ctx=ctx), "DOMAIN_CONFLICT")

    def test_schedule_hole_rejects_before_random_draw_or_ontology_skip(self):
        template = ReliefTemplate.model_validate({
            "system_name": "gap", "display_name": "Gap", "context": "road_shoulder",
            "conditions": [{"terrain": "plains", "cases": [
                {"policy": "slope_down", "bands": [
                    {"delta_z_min": 1, "delta_z_max": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"delta_z_min": 5, "delta_z_max": None, "slope_weight": 1.0, "sheer_weight": 0.0}]},
                {"policy": "slope_up", "bands": [
                    {"delta_z_min": 1, "delta_z_max": None, "slope_weight": 1.0, "sheer_weight": 0.0}]},
                {"policy": "slope_none", "bands": []}]}]})
        before = template.model_dump()
        for grade in (grade_from_template, grade_constrained):
            with patch("app.application.worldData.generators.terrain.relief.pick.gradePass.kind_roll") as roll:
                self.assert_policy_error(lambda ctx: grade(template=template, template_uid="gap",
                    terrain_key="plains", dz=3, world_seed="seed", site_id="site",
                    resolve_ctx=ctx), "DOMAIN_SCHEDULE_HOLE")
            roll.assert_not_called()
            self.assertEqual(template.model_dump(), before)

    def test_normal_absence_and_replay_are_preserved(self):
        registry = WorldCanalTemplateRegistry.canonical_defaults()
        self.assertIsNone(resolve_knobs_canal(earthen_canal=None, structure_canal=None,
            structure_refs=(), registry=registry))
        reg = WorldReliefTemplateRegistry.model_validate([{"context": "mountain", "system_template_uid": uid}
                                                         for uid in ("one", "two")])
        for mode in ("random", "round_robin"):
            policy = WorldReliefPickPolicy(mountain=ReliefContextPickPolicy(mode=mode))
            def replay():
                return [pick_template(context="mountain", registry=reg, world_policy=policy,
                    world_seed="seed", site_id=f"site-{i}", occurrence_seq=i) for i in range(5)]
            self.assertEqual(replay(), replay())
            if mode == "round_robin":
                self.assertEqual([p.template_uid for p in replay()], ["one", "two", "one", "two", "one"])
