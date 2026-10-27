"""G2 leaf schemas and the single linked water cascade, before G10-A activation."""

from math import inf, nan
from unittest import TestCase
from unittest.mock import patch

from pydantic import BaseModel, Field, ValidationError

from app.application.cascade.cascadeLink import EmptyLink, Link
from app.application.cascade.contextResolver import extend, scope_sequence
from app.application.policy.policyRead import PolicyReader
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, resolve_model, resolve_patch
from app.dataModel.cascade.cascadeGraph import bind_field, ordered_chain
from app.dataModel.cascade.cascadeSpec import ChannelKind, FieldRef
from app.dataModel.cascade.cascadeVerify import verify_cascade_contract
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
from app.dataModel.hydrology.generation.waterGenerationSettings import (
    BodyWaterGenerationSettings, CategoryWaterGenerationSettings, WorldWaterGenerationSettings,
    WaterGenerationSettings, WATER_AUTORESOLVE, WATER_FRACTION, WATER_STRATEGY,
)
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.policy.policyBindings import PolicyInputs, PolicyFacts, PolicySource
from app.dataModel.policy.policyReferences import DirectValueRef
from app.dataModel.policy.policyFacts import KnownFact
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy

MODELS = (WaterGenerationSettings, WorldWaterGenerationSettings, CategoryWaterGenerationSettings,
          BodyWaterGenerationSettings)


def world_context(settings=None, *, defaults=None):
    root = WaterGenerationContext.root(object(), default_sources=defaults)
    return extend(root, Link(Scope.WORLD, settings or WorldWaterGenerationSettings()))


class WaterGenerationSettingsTests(TestCase):
    def test_all_source_models_have_the_same_nullable_fields(self):
        for model in MODELS:
            empty = model()
            explicit = model(water_fraction=None, autoresolve=None, strategy=None)
            self.assertEqual(set(model.model_fields), {"water_fraction", "autoresolve", "strategy"})
            self.assertEqual(empty.model_dump(), dict.fromkeys(model.model_fields))
            self.assertEqual(empty.model_fields_set, set())
            self.assertEqual(explicit.model_fields_set, set(model.model_fields))
            self.assertEqual(model.model_validate_json(empty.model_dump_json()), empty)

    def test_missing_null_zero_and_false_survive_shared_wire_roundtrip(self):
        for model in MODELS:
            for wire in ({}, {"water_fraction": None, "autoresolve": None, "strategy": None},
                         {"water_fraction": 0, "autoresolve": False, "strategy": "authored_region"}):
                with self.subTest(model=model.__name__, wire=wire):
                    value = resolve_model(model, wire, ctx=ResolveContext(validate_only=True))
                    restored = model.model_validate_json(value.model_dump_json(exclude_unset=True))
                    self.assertEqual(restored, value)
                    self.assertEqual(restored.model_fields_set, set(wire))
                    if wire.get("water_fraction") == 0:
                        self.assertEqual(restored.water_fraction, 0.0)
                        self.assertIs(restored.autoresolve, False)
                        self.assertIs(restored.strategy, Strategy.AUTHORED_REGION)

    def test_invalid_fraction_never_becomes_a_default(self):
        for model in MODELS:
            for value in (True, False, "0.5", -0.01, 1.01, nan, inf, -inf):
                with self.subTest(model=model.__name__, value=value), self.assertRaises(ValidationError):
                    model(water_fraction=value)

    def test_strict_bool_closed_enum_and_extra_fields(self):
        for model in MODELS:
            for field, values in (("autoresolve", (0, 1, "false", "true")),
                                  ("strategy", (True, 0, "noise", "unknown"))):
                for value in values:
                    with self.subTest(model=model.__name__, field=field, value=value), self.assertRaises(ValidationError):
                        model.model_validate({field: value})
            with self.assertRaises(ValidationError):
                model.model_validate({"effective_fraction": 0.6})

    def test_shared_resolver_reports_invalid_enum_without_fallback(self):
        ctx = ResolveContext(validate_only=True)
        with self.assertRaises(UnresolvedModelError):
            resolve_model(WorldWaterGenerationSettings, {"strategy": "invalid"}, ctx=ctx)
        self.assertTrue(ctx.errors)
        self.assertEqual(ctx.errors[0].code, "UNKNOWN_ENUM")

    def test_shared_resolver_keeps_numeric_and_boolean_constraints(self):
        for wire in ({"water_fraction": True}, {"water_fraction": "0.5"},
                     {"water_fraction": 2.0}, {"autoresolve": 1}, {"autoresolve": "false"}):
            ctx = ResolveContext(validate_only=True)
            with self.subTest(wire=wire), self.assertRaises(UnresolvedModelError):
                resolve_model(WorldWaterGenerationSettings, wire, ctx=ctx)
            self.assertTrue(ctx.errors)

    def test_embedded_settings_bind_directly_without_a_projection(self):
        class OwnerFixture(BaseModel):
            generation: WorldWaterGenerationSettings = Field(default_factory=WorldWaterGenerationSettings)
        owner = resolve_model(OwnerFixture, {"generation": {"water_fraction": 0.3}}, ctx=ResolveContext(validate_only=True))
        link = Link(Scope.WORLD, owner.generation)
        self.assertIs(link.obj, owner.generation)
        result = extend(WaterGenerationContext.root(owner), link)
        self.assertEqual(result.water_fraction, 0.3)
        self.assertEqual(result.provenance["water_fraction"], (Scope.WORLD, "WorldWaterGenerationSettings.water_fraction"))
        self.assertEqual(set(owner.model_dump()), {"generation"})

    def test_default_is_not_logged_again_at_empty_deeper_scopes(self):
        with patch("app.application.cascade.contextResolver.log_default_applied") as logged:
            context = world_context()
            context = extend(context, EmptyLink(Scope.CATEGORY))
            context = extend(context, EmptyLink(Scope.WATER_BODY))
        self.assertEqual(logged.call_count, 3)
        self.assertEqual((context.water_fraction, context.autoresolve, context.strategy), (0.6, False, Strategy.CONTINENTAL_NOISE))

    def test_patch_presence_and_null_preserve_inheritance(self):
        ctx = ResolveContext(validate_only=True)
        self.assertEqual(resolve_patch(WorldWaterGenerationSettings, {}, ctx=ctx), {})
        self.assertEqual(resolve_patch(WorldWaterGenerationSettings, {"autoresolve": None}, ctx=ctx), {"autoresolve": None})
        original = WorldWaterGenerationSettings(water_fraction=0.3, autoresolve=True)
        changes = resolve_patch(WorldWaterGenerationSettings, {"water_fraction": 0, "autoresolve": False}, ctx=ctx)
        merged = WorldWaterGenerationSettings.model_validate({**original.model_dump(), **changes})
        self.assertEqual((merged.water_fraction, merged.autoresolve), (0.0, False))
        with self.assertRaises(UnresolvedModelError):
            resolve_patch(WorldWaterGenerationSettings, {"autoresolve": 1}, ctx=ctx)

    def test_canonical_defaults_and_root_are_lazy(self):
        defaults = WaterGenerationDefaults.canonical_defaults()
        self.assertEqual(defaults.water_fraction, 0.6)
        self.assertIs(defaults.autoresolve, False)
        self.assertIs(defaults.strategy, Strategy.CONTINENTAL_NOISE)
        root = WaterGenerationContext.root(object())
        self.assertIs(root.level, Scope.ROOT)
        self.assertIsNone(root.water_fraction)
        self.assertIsNone(root.autoresolve)
        self.assertIsNone(root.strategy)
        self.assertFalse(root.provenance)
        self.assertFalse(root._node_results)

    def test_complete_graph_is_verified_and_has_only_value_nodes(self):
        verify_cascade_contract(WaterGenerationContext)
        for param in (WATER_FRACTION, WATER_AUTORESOLVE, WATER_STRATEGY):
            chain = ordered_chain(param)
            self.assertEqual([n.level for _, n, _ in chain], [Scope.WATER_BODY, Scope.CATEGORY, Scope.WORLD])
            self.assertTrue(all(c.kind is ChannelKind.VALUE for _, _, c in chain))
            self.assertIsNone(param.materialize)
            self.assertIsNone(param.fold)
            bound = bind_field(param.default_source.ref)
            self.assertIs(bound.model, WaterGenerationDefaults)
            self.assertEqual(bound.field, param.field)
        self.assertEqual(scope_sequence(WaterGenerationContext.root(object())),
                         (Scope.ROOT, Scope.WORLD, Scope.CATEGORY, Scope.WATER_BODY))

    def test_world_channels_win_and_do_not_mutate_authored_settings(self):
        settings = WorldWaterGenerationSettings(water_fraction=0, autoresolve=False, strategy=Strategy.PLATE_NOISE)
        before = settings.model_dump()
        with patch("app.application.cascade.contextResolver._MATERIALIZE", {}), \
             patch("app.application.cascade.contextResolver._FOLDS", {}):
            context = world_context(settings)
        self.assertEqual((context.water_fraction, context.autoresolve, context.strategy), (0.0, False, Strategy.PLATE_NOISE))
        self.assertEqual(settings.model_dump(), before)
        self.assertEqual(context.provenance["strategy"], (Scope.WORLD, "WorldWaterGenerationSettings.strategy"))

    def test_resolved_context_is_a_valid_shared_policy_source(self):
        context = world_context(WorldWaterGenerationSettings(autoresolve=False))
        binding = PolicySource(WaterGenerationContext, context, ("resolved",))
        reference = DirectValueRef(FieldRef(lambda: WaterGenerationContext, lambda c: c.autoresolve))
        reader = PolicyReader(PolicyInputs(models=(binding,)), PolicyFacts())
        self.assertFalse(reader.validate())
        observed = reader.read(reference)
        self.assertIsInstance(observed, KnownFact)
        self.assertIs(observed.value, False)

    def test_defaults_are_read_from_bound_pojo_and_missing_is_explicit(self):
        defaults = WaterGenerationDefaults(water_fraction=0.8, autoresolve=True, strategy=Strategy.PLATE)
        result = world_context(defaults=(defaults,))
        self.assertEqual((result.water_fraction, result.autoresolve, result.strategy), (0.8, True, Strategy.PLATE))
        self.assertEqual(result.provenance["water_fraction"], (Scope.ROOT, "default:canonical_default"))
        with self.assertRaisesRegex(ValueError, "got 0"):
            world_context(defaults=())
        with self.assertRaisesRegex(ValueError, "got 2"):
            world_context(defaults=(defaults, defaults))

    def test_category_body_inherit_and_siblings_are_independent(self):
        world = world_context(WorldWaterGenerationSettings(water_fraction=0.9, autoresolve=True, strategy=Strategy.PLATE))
        category = extend(world, Link(Scope.CATEGORY, CategoryWaterGenerationSettings(water_fraction=0.2)))
        body = extend(category, Link(Scope.WATER_BODY, BodyWaterGenerationSettings(autoresolve=False)))
        sibling = extend(category, EmptyLink(Scope.WATER_BODY))
        self.assertEqual((body.water_fraction, body.autoresolve, body.strategy), (0.2, False, Strategy.PLATE))
        self.assertIs(sibling.autoresolve, True)
        self.assertIs(world.autoresolve, True)
        self.assertEqual(body.provenance["water_fraction"][0], Scope.CATEGORY)
        self.assertEqual(body.provenance["autoresolve"][0], Scope.WATER_BODY)
        self.assertEqual(body.provenance["strategy"][0], Scope.WORLD)

    def test_frozen_revalidated_models_reject_forged_copy(self):
        value = WorldWaterGenerationSettings()
        with self.assertRaises(ValidationError):
            value.autoresolve = True
        forged = value.model_copy(update={"water_fraction": inf})
        with self.assertRaises(ValidationError):
            WorldWaterGenerationSettings.model_validate(forged)

    def test_production_schema_and_defaults_are_not_activated(self):
        self.assertNotIn("generation", WorldHydrology.model_fields)
        active = WorldHydrology()
        self.assertTrue(active.default_seas.autoresolve_coastal_sea)
        self.assertTrue(active.default_seas.autoresolve_open_ocean)
        self.assertEqual(active.default_seas.placement_specificity, 0)
        self.assertEqual(active.default_lakes.placement_specificity, 0)
