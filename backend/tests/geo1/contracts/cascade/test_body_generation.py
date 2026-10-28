"""G3: embedded body overrides on the three authored source shapes, isolated until G10-A."""

from copy import deepcopy
from itertools import product
from math import inf, nan
from unittest import TestCase

from pydantic import ValidationError

from app.application.cascade.cascadeLink import EmptyLink, Link
from app.application.cascade.contextResolver import extend
from app.application.jsonValidation.resolve import ResolveContext, resolve_model, resolve_patch
from app.application.policy.declarations.compiler import compile_value_policy
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.cascade.cascadeGraph import ordered_chain
from app.dataModel.cascade.cascadeVerify import verify_cascade_contract
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import (
    BodyGenerationFields, BodyWaterGenerationSettings, CategoryWaterGenerationSettings,
    WorldHydrologyGenerationFields, WorldWaterGenerationSettings, WATER_AUTORESOLVE, WATER_FRACTION, WATER_STRATEGY,
)
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.policy.hydrologyPolicyDefinition import HYDROLOGY_GENERATION_POLICY
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs, PolicySource
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


class BasinInput(DeclaredBasin, BodyGenerationFields):
    """Future owner composition; not exported from the active source model module."""


class CoastlineInput(DeclaredCoastline, BodyGenerationFields):
    pass


class LakeInput(DeclaredLake, BodyGenerationFields):
    pass


def basin(settings):
    return BasinInput(location_uid="basin-source", kind=BasinKind.LAKE, floor_z=-4,
        footprint=BboxShape(x_min=0, y_min=0, x_max=4, y_max=3), generation=settings)


def coastline(settings):
    return CoastlineInput(location_uid="coast-source", kind=BasinKind.SEA,
        path=(HydrologyWaypoint(x=0, y=0), HydrologyWaypoint(x=4, y=0)), generation=settings)


def lake(settings):
    return LakeInput(location_uid="lake-source", shoreline=(HydrologyWaypoint(x=0, y=0),
        HydrologyWaypoint(x=4, y=0), HydrologyWaypoint(x=4, y=3)), generation=settings)


FACTORIES = (basin, coastline, lake)


def parent(world, category=None):
    context = extend(WaterGenerationContext.root(world), Link(Scope.WORLD, world))
    return extend(context, EmptyLink(Scope.CATEGORY) if category is None else Link(Scope.CATEGORY, category))


class BodyGenerationTests(TestCase):
    def test_missing_empty_and_explicit_null_leaf_keep_authored_presence(self):
        for factory in FACTORIES:
            prototype = factory(BodyWaterGenerationSettings())
            raw = prototype.model_dump(mode="json", exclude={"generation"})
            for extra, expected in (({}, {}), ({"generation": {}}, {"generation": {}}),
                                    ({"generation": {"autoresolve": None}}, {"generation": {"autoresolve": None}})):
                value = resolve_model(type(prototype), raw | extra, ctx=ResolveContext(validate_only=True))
                self.assertIsNone(value.generation.water_fraction)
                self.assertIsNone(value.generation.autoresolve)
                self.assertIsNone(value.generation.strategy)
                exported = value.model_dump(mode="json", exclude_unset=True)
                self.assertEqual({k: exported[k] for k in expected}, expected)
                if not extra:
                    self.assertNotIn("generation", exported)
                restored = type(value).model_validate_json(value.model_dump_json(exclude_unset=True))
                self.assertEqual(restored, value)
                self.assertEqual(restored.generation.model_fields_set, value.generation.model_fields_set)

    def test_all_section_4_3_examples_on_each_source(self):
        cases = ((WorldWaterGenerationSettings(water_fraction=0.75), BodyWaterGenerationSettings(), 0.75, False),
                 (WorldWaterGenerationSettings(water_fraction=0.75), BodyWaterGenerationSettings(water_fraction=0.30), 0.30, False),
                 (WorldWaterGenerationSettings(), BodyWaterGenerationSettings(), 0.60, False),
                 (WorldWaterGenerationSettings(water_fraction=0), BodyWaterGenerationSettings(), 0, False),
                 (WorldWaterGenerationSettings(autoresolve=True), BodyWaterGenerationSettings(autoresolve=False), 0.60, False),
                 (WorldWaterGenerationSettings(autoresolve=False), BodyWaterGenerationSettings(autoresolve=True), 0.60, True),
                 (WorldWaterGenerationSettings(autoresolve=True), BodyWaterGenerationSettings(autoresolve=None), 0.60, True))
        for factory, (world, overrides, fraction, autoresolve) in product(FACTORIES, cases):
            with self.subTest(source=factory.__name__, world=world, body=overrides):
                source = factory(overrides)
                link = Link(Scope.WATER_BODY, source.generation)
                self.assertIs(link.obj, source.generation)
                result = extend(parent(world), link)
                self.assertEqual(result.water_fraction, fraction)
                self.assertIs(result.autoresolve, autoresolve)
                self.assertIs(result.strategy, Strategy.CONTINENTAL_NOISE)

    def test_category_inheritance_body_override_and_independent_siblings(self):
        category = CategoryWaterGenerationSettings(water_fraction=0.4, autoresolve=False, strategy=Strategy.PLATE)
        shared_parent = parent(WorldWaterGenerationSettings(water_fraction=0.8, autoresolve=True), category)
        for factory in FACTORIES:
            inherited = factory(BodyWaterGenerationSettings())
            overridden = factory(BodyWaterGenerationSettings(water_fraction=0, autoresolve=True, strategy=Strategy.AUTHORED_REGION))
            result = extend(shared_parent, Link(Scope.WATER_BODY, overridden.generation))
            sibling = extend(shared_parent, Link(Scope.WATER_BODY, inherited.generation))
            self.assertEqual((result.water_fraction, result.autoresolve, result.strategy), (0, True, Strategy.AUTHORED_REGION))
            self.assertEqual((sibling.water_fraction, sibling.autoresolve, sibling.strategy), (0.4, False, Strategy.PLATE))
            self.assertEqual(result.provenance["water_fraction"][0], Scope.WATER_BODY)
            self.assertEqual(result.provenance["strategy"], (Scope.WATER_BODY, "BodyWaterGenerationSettings.strategy"))
            self.assertEqual(sibling.provenance["autoresolve"][0], Scope.CATEGORY)
        self.assertEqual((shared_parent.water_fraction, shared_parent.autoresolve), (0.4, False))

    def test_shared_boundary_preview_runtime_and_roundtrip_are_identical(self):
        spec = compile_value_policy(HYDROLOGY_GENERATION_POLICY, (WorldHydrologyGenerationFields, WaterGenerationContext))
        root = WorldHydrologyGenerationFields(generation=WorldWaterGenerationSettings(autoresolve=True))
        for factory in FACTORIES:
            source = factory(BodyWaterGenerationSettings(water_fraction=0, autoresolve=False, strategy=Strategy.PLATE_NOISE))
            raw = source.model_dump(mode="json")
            before = deepcopy(raw)
            results = []
            for validate_only in (True, False):
                ctx = ResolveContext.for_import(validate_only=validate_only)
                restored = resolve_model(type(source), raw, ctx=ctx)
                resolved = extend(parent(root.generation), Link(Scope.WATER_BODY, restored.generation))
                decision = PolicyResolver().resolve(spec, PolicyInputs(models=(
                    PolicySource(WorldHydrologyGenerationFields, root, ("hydrology",)),
                    PolicySource(WaterGenerationContext, resolved, ("resolved",)),)), PolicyFacts(),
                    mode=ResolutionMode.VALIDATE_ONLY if validate_only else ResolutionMode.RUNTIME)
                self.assertIs(decision.require_behavior(), Mode.DECLARED_ONLY)
                self.assertFalse(ctx.errors)
                results.append((restored, resolved.water_fraction, resolved.strategy, resolved.provenance, decision))
            self.assertEqual(results[0], results[1])
            self.assertEqual(raw, before)

    def test_overrides_do_not_change_source_identity_or_geometry(self):
        for factory in FACTORIES:
            owner = factory(BodyWaterGenerationSettings(water_fraction=0, autoresolve=True))
            before = owner.model_dump(mode="json", exclude={"generation"})
            extend(parent(WorldWaterGenerationSettings()), Link(Scope.WATER_BODY, owner.generation))
            self.assertEqual(owner.model_dump(mode="json", exclude={"generation"}), before)
            self.assertEqual(owner.location_uid, before["location_uid"])
            self.assertNotIn("generation", before)

    def test_invalid_embedded_settings_are_rejected_by_composed_owner(self):
        invalid = ({"water_fraction": True}, {"water_fraction": -0.1}, {"water_fraction": 1.1},
                   {"water_fraction": inf}, {"water_fraction": nan}, {"autoresolve": 1},
                   {"autoresolve": "false"}, {"strategy": "unknown"}, {"unknown": True})
        for factory in FACTORIES:
            prototype = factory(BodyWaterGenerationSettings())
            raw = prototype.model_dump(mode="json", exclude={"generation"})
            for generation in (*invalid, None):
                with self.subTest(source=factory.__name__, generation=generation), self.assertRaises(ValidationError):
                    type(prototype).model_validate(raw | {"generation": generation})
            with self.assertRaises(ValidationError):
                type(prototype).model_validate(raw | {"generation": BodyWaterGenerationSettings().model_copy(update={"autoresolve": 1})})

    def test_shared_patch_boundary_preserves_missing_and_resets_null_to_inheritance(self):
        for factory in FACTORIES:
            owner = factory(BodyWaterGenerationSettings(water_fraction=0.2, autoresolve=False))
            ctx = ResolveContext(validate_only=True, path_prefix=("generation",))
            self.assertEqual(resolve_patch(BodyWaterGenerationSettings, {}, ctx=ctx), {})
            changes = resolve_patch(BodyWaterGenerationSettings, {"water_fraction": None, "autoresolve": None}, ctx=ctx)
            patched = BodyWaterGenerationSettings.model_validate(owner.generation.model_dump() | changes)
            result = extend(parent(WorldWaterGenerationSettings(water_fraction=0.7, autoresolve=True)), Link(Scope.WATER_BODY, patched))
            self.assertEqual((result.water_fraction, result.autoresolve), (0.7, True))

    def test_existing_owner_validators_are_retained(self):
        with self.assertRaises(ValidationError):
            BasinInput(location_uid="invalid", kind=BasinKind.LAKE, floor_z=4, z_water_level=2,
                       footprint=BboxShape(x_min=0, y_min=0, x_max=2, y_max=2))
        with self.assertRaises(ValidationError):
            CoastlineInput(location_uid="invalid", kind=BasinKind.SEA, path=(HydrologyWaypoint(x=0, y=0),))

    def test_procedural_caller_uses_same_owner_field_and_no_duplicate_graph_nodes(self):
        owner = BodyGenerationFields(generation=BodyWaterGenerationSettings(autoresolve=True))
        result = extend(parent(WorldWaterGenerationSettings()), Link(Scope.WATER_BODY, owner.generation))
        self.assertIs(result.autoresolve, True)
        verify_cascade_contract(WaterGenerationContext)
        for param in (WATER_FRACTION, WATER_AUTORESOLVE, WATER_STRATEGY):
            self.assertEqual(len(ordered_chain(param)), 3)
        self.assertEqual(set(BodyGenerationFields.model_fields), {"generation"})

    def test_active_declared_sources_and_world_export_are_unchanged(self):
        for model in (DeclaredBasin, DeclaredCoastline, DeclaredLake):
            self.assertNotIn("generation", model.model_fields)
        self.assertNotIn("generation", WorldHydrology.model_fields)
        self.assertNotIn("generation", WorldHydrology.canonical_empty().model_dump())
