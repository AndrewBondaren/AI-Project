from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.worldData.generators.terrain.relief.surfaceCoatingSupport import SurfaceCoatingSupportProvider, CoatingPlanProvider
from app.application.worldData.planning.validation.surfacePlanValidator import SurfacePlanValidator
from app.application.jsonValidation.resolve import ResolveContext
from app.dataModel.policy.policyFacts import UnknownFact
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.terrain.relief.specs import ReliefSideSpec
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceSupportPlan, SurfaceAspect
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage, CoverageSpan
from app.dataModel.terrainMasks.mountain.specs import MountainSpec, MountainFormBySides
from app.dataModel.terrainMasks.regions import PlainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.support_sources.fixtures import captured
from tests.geo1.coating.fixtures import prepared, coating_input


def coverage(x0=0, x1=4, y=0):
    return RegionCoverage(region_uid="world", spans=(CoverageSpan(y=y, x0=x0, x1=x1),))


class SupportProviderTests(TestCase):
    def test_facts_replay_without_world_pack_or_mill_reads(self):
        request, deps = prepared()
        before = deps.hydrology.payload
        with patch("app.application.jsonValidation.terrain", side_effect=AssertionError("live world read")):
            full = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage())
            left = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(0, 2))
            right = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(2, 4))
        self.assertEqual(full, left + right)
        self.assertEqual(deps.hydrology.payload, before)
        self.assertTrue(all(f.aspect.value is SurfaceAspect.HORIZONTAL for f in full))

    def test_stamped_sheer_has_explicit_face_and_keeps_rock(self):
        peak = MountainSpec(origin_x_m=0, origin_y_m=0, radius_m=3, form=MountainFormBySides(side_count=4),
                            sides=tuple(ReliefSideSpec(kind=ReliefSideKind.SHEER) for _ in range(4)))
        request, deps = prepared(entries=(peak,))
        facts = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(2, 3))
        self.assertEqual(facts[0].aspect.value, SurfaceAspect.RELIEF_FACE)
        self.assertIsNotNone(facts[0].face)
        self.assertEqual(facts[0].side_kind.value, ReliefSideKind.SHEER)
        self.assertEqual(facts[0].material.value, "stone")

    def test_unknown_substrate_is_never_guessed_from_material_key(self):
        inputs = captured()
        inputs = replace(inputs, materials=tuple(replace(m, substrate=None) for m in inputs.materials))
        request, deps = prepared(inputs)
        facts = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(0, 1))
        self.assertIsInstance(facts[0].substrate, UnknownFact)

    def test_declared_region_material_and_tombstone_use_snapshot(self):
        from app.application.worldData.masks.regionIdentity import declared_region_identity
        from app.dataModel.regions.regionState import RegionState
        spec = PlainSpec(name="ice-patch", shape=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1))
        inputs = captured(masks=WorldTerrainMasks(declared_regions=(spec,)))
        uid = declared_region_identity("world", spec).region_uid
        state = RegionState(region_uid=uid, current_type="forest")
        entries = tuple(replace(e, default_material="stone") if e.key == "forest" else e for e in inputs.terrain_entries)
        for states, expected in (((), "earth"), ((state,), "stone"), ((replace(state, tombstone=True),), "stone")):
            with self.subTest(states=states):
                request, deps = prepared(replace(inputs, region_states=states, terrain_entries=entries))
                facts = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(0, 1))
                self.assertEqual(facts[0].material.value, expected)

    def test_wrapped_side_geometry_uses_the_unrolled_frame(self):
        from app.dataModel.topology.worldTopology import WorldTopology
        from app.dataModel.topology.worldBounds import WorldBounds
        peak = MountainSpec(origin_x_m=-1, origin_y_m=0, radius_m=2, form=MountainFormBySides(side_count=4),
                            sides=tuple(ReliefSideSpec(kind=ReliefSideKind.SHEER) for _ in range(4)))
        inputs = replace(captured(), topology=WorldTopology(mode="wrapped", bounds=WorldBounds(x_min=0, x_max=1, y_min=0, y_max=1)))
        request, deps = prepared(inputs, entries=(peak,))
        facts = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(2, 3))
        self.assertEqual(facts[0].aspect.value, SurfaceAspect.RELIEF_FACE)
        self.assertEqual(facts[0].side_kind.value, ReliefSideKind.SHEER)

    def test_missing_shore_evidence_is_not_silently_dropped(self):
        _, deps = prepared()
        with self.assertRaises(ValueError):
            CoatingPlanProvider.plan(coating_input(), SurfaceSupportPlan(facts=()), deps.hydrology.payload, fine_span=2)

    def test_postriver_change_requires_new_geometry_evidence(self):
        from app.dataModel.terrain.relief.planning.reliefPlan import RiverBedRecord
        from app.dataModel.spatial.grid.coordinateTypes import FineXY
        from app.dataModel.planning.contracts.planDependency import PlanDependency
        from tests.geo1.coating.fixtures import envelope
        request, deps = prepared()
        river = replace(deps.river_relief.payload, fine_surface_z=(((0, 0), -2),),
            fine_beds=(RiverBedRecord[FineXY](river_uid="river", bed_z=(((0, 0), -2),)),))
        river_envelope = envelope("river_relief", river, deps.river_relief.dependencies)
        hydro = replace(deps.hydrology, dependencies=(PlanDependency(slot="river_relief", ref=river_envelope.ref),))
        deps = replace(deps, river_relief=river_envelope, hydrology=hydro)
        request = replace(request, dependencies=tuple(PlanDependency(slot=name, ref=getattr(deps, name).ref)
            for name in sorted(deps.__dataclass_fields__)))
        facts = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(0, 1))
        self.assertIsInstance(facts[0].aspect, UnknownFact)
        self.assertIsInstance(facts[0].substrate, UnknownFact)

    def test_relief_projection_without_side_proof_does_not_invent_horizontal(self):
        from app.dataModel.terrain.relief.planning.reliefPlan import LightRavineCell
        from app.dataModel.spatial.grid.coordinateTypes import LightCellRef
        request, deps = prepared(light_ravines=(LightRavineCell(cell=LightCellRef(0, 0, 0, 0), surface_z=-1),))
        facts = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(0, 1))
        self.assertIsInstance(facts[0].aspect, UnknownFact)

    def test_missing_final_surface_reference_is_a_dependency_error(self):
        request, deps = prepared()
        bad = replace(deps, hydrology=replace(deps.hydrology, dependencies=()))
        with self.assertRaises(ValueError):
            SurfaceCoatingSupportProvider.facts(request, bad, cells=coverage(0, 1))

    def test_missing_member_and_structural_material_are_unknown(self):
        from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
        from tests.geo1.support_sources.fixtures import UID, members, template
        body = template()
        member = MountainTemplateInput(template_uid=UID, context=body.context, side_recipe=body.side_recipe)
        peak = MountainSpec(origin_x_m=0, origin_y_m=0, radius_m=3, form=MountainFormBySides(side_count=4),
                            sides=tuple(ReliefSideSpec(kind=ReliefSideKind.SHEER) for _ in range(4)))
        inputs = replace(captured(), templates=())
        request, deps = prepared(inputs, entries=(peak,), layout_templates=(member,))
        self.assertIsInstance(SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(2, 3))[0].aspect, UnknownFact)
        inputs = captured(templates=members(replace(body, structure_refs=("stone-wall",))))
        request, deps = prepared(inputs, entries=(peak,), layout_templates=(member,))
        facts = SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(2, 3))
        self.assertIsInstance(facts[0].material, UnknownFact)
        self.assertIsInstance(facts[0].substrate, UnknownFact)

    def test_foreign_dependencies_and_noncanonical_cells_rejected(self):
        request, deps = prepared()
        foreign = replace(deps.hydrology, ref=replace(deps.hydrology.ref, key=replace(deps.hydrology.ref.key, world_uid="other")))
        with self.assertRaises(ValueError):
            SurfaceCoatingSupportProvider.facts(request, replace(deps, hydrology=foreign), cells=coverage())
        with self.assertRaises(ValueError):
            SurfaceCoatingSupportProvider.facts(request, deps, cells=coverage(-1, 0))

    def test_readonly_validation_retains_runtime_fallback_issue(self):
        from tests.geo1.coating.test_policy import fact
        _, deps = prepared()
        support = SurfaceSupportPlan(facts=(fact(substrate=None),))
        runtime = CoatingPlanProvider.plan(coating_input(), support, deps.hydrology.payload, fine_span=2)
        preview = CoatingPlanProvider.plan(coating_input(ResolutionMode.VALIDATE_ONLY), support, deps.hydrology.payload, fine_span=2)
        ctx = ResolveContext(validate_only=True)
        SurfacePlanValidator().validate_coating(runtime.payload, ctx=ctx)
        self.assertEqual(tuple(ctx.errors), preview.payload.cells[0].decision.issues)
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logs:
            SurfacePlanValidator().validate_coating(runtime.payload, ctx=ResolveContext())
        self.assertTrue(any("WarningError" in line for line in logs.output))
