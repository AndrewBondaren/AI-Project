from unittest import TestCase
from app.application.worldData.generators.terrain.relief.surfaceCoatingSupport import CoatingPlanProvider, unknown_support
from app.dataModel.policy.policyFacts import KnownFact
from app.dataModel.policy.policyEnums import PolicyState, PolicyDisableReason
from app.dataModel.materials.enums.materialSubstrateKind import MaterialSubstrateKind as Substrate
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import (
    SurfaceAspect, SurfaceCoatingFacts, SurfaceCoatingAction as Action, SurfaceSupportPlan,
)
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.coating.fixtures import prepared, coating_input


def fact(aspect=SurfaceAspect.RELIEF_FACE, side=ReliefSideKind.SHEER, substrate=Substrate.ROCK):
    request, deps = prepared()
    return SurfaceCoatingFacts(world_uid="world", support_input_fingerprint=request.key.input_fingerprint,
        cell=(0, 0), face=None if aspect is SurfaceAspect.HORIZONTAL else Facing.NORTH,
        aspect=KnownFact(value=aspect) if aspect is not None else unknown_support((0, 0), "aspect", "unknown geometry"),
        side_kind=KnownFact(value=side), material=KnownFact(value="stone"),
        substrate=KnownFact(value=substrate) if substrate is not None else unknown_support((0, 0), "substrate", "unknown substrate"),
        geometry_ref=deps.river_relief.ref, material_source_path=("materials", "stone"))


class CoatingPolicyTests(TestCase):
    def resolve(self, facts, mode=ResolutionMode.RUNTIME, target=None):
        _, deps = prepared()
        return CoatingPlanProvider.plan(coating_input(mode, target), SurfaceSupportPlan(facts=(facts,)),
                                       deps.hydrology.payload, fine_span=2)

    def test_truth_table(self):
        cases = ((SurfaceAspect.HORIZONTAL, ReliefSideKind.SHEER, Substrate.ROCK, True),
                 (SurfaceAspect.RELIEF_FACE, ReliefSideKind.SLOPE, Substrate.ROCK, True),
                 (SurfaceAspect.RELIEF_FACE, ReliefSideKind.SHEER, Substrate.ROCK, False),
                 (SurfaceAspect.RELIEF_FACE, ReliefSideKind.SHEER, Substrate.OTHER, True))
        for aspect, side, substrate, allow in cases:
            with self.subTest(aspect=aspect, side=side, substrate=substrate):
                result = self.resolve(fact(aspect, side, substrate))
                decision = result.payload.cells[0].decision
                self.assertEqual(decision.behavior, Action.APPLY_SHORE_SURFACE if allow else Action.KEEP_EXISTING_SURFACE)
                self.assertFalse(result.diagnostics)
                if not allow:
                    self.assertEqual(decision.reasons[0].common_reason, PolicyDisableReason.POLICY_FORBID)
                    self.assertIsNone(result.payload.cells[0].target)
                else:
                    self.assertEqual(result.payload.cells[0].target.terrain, "shore")
                    self.assertEqual(result.payload.cells[0].target.material, "sand")

    def test_unknown_is_validation_error_and_runtime_fallback_with_identical_issue(self):
        for facts in (fact(substrate=None), fact(aspect=None)):
            valid = self.resolve(facts, ResolutionMode.VALIDATE_ONLY)
            runtime = self.resolve(facts)
            self.assertEqual(valid.payload.cells[0].decision.state, PolicyState.UNRESOLVED)
            self.assertEqual(runtime.payload.cells[0].decision.behavior, Action.KEEP_EXISTING_SURFACE)
            self.assertEqual(valid.payload.cells[0].decision.issues, runtime.payload.cells[0].decision.issues)
            self.assertTrue(runtime.diagnostics)

    def test_known_nonrock_short_circuits_unknown_geometry(self):
        self.assertEqual(self.resolve(fact(aspect=None, substrate=Substrate.OTHER)).payload.cells[0].decision.behavior,
                         Action.APPLY_SHORE_SURFACE)

    def test_horizontal_short_circuits_unknown_substrate(self):
        self.assertEqual(self.resolve(fact(aspect=SurfaceAspect.HORIZONTAL, substrate=None)).payload.cells[0].decision.behavior,
                         Action.APPLY_SHORE_SURFACE)

    def test_unknown_target_cannot_be_hidden_by_default_selection(self):
        result = self.resolve(fact(aspect=SurfaceAspect.HORIZONTAL), target=unknown_support((0, 0), "target", "missing target"))
        self.assertEqual(result.payload.cells[0].decision.behavior, Action.KEEP_EXISTING_SURFACE)
        self.assertTrue(result.diagnostics)

    def test_coating_decision_keeps_hydrology_identity_role_and_level(self):
        _, deps = prepared()
        hydro = deps.hydrology.payload
        before = hydro.model_dump()
        CoatingPlanProvider.plan(coating_input(), SurfaceSupportPlan(facts=(fact(),)), hydro, fine_span=2)
        self.assertEqual(hydro.model_dump(), before)
        self.assertEqual(hydro.sparse_fine_hydro[0][1].water_body_uid, "body")
        self.assertEqual(hydro.sparse_fine_hydro[0][1].z_water_level, 5)
