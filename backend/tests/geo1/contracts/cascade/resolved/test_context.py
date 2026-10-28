"""G4-I: generic projection, detached provenance and no repeated resolution."""

from typing import Annotated
from unittest import TestCase
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, PrivateAttr, StrictInt, computed_field

from app.application.cache.service.cacheService import validate_immutable as cache_validate_immutable
from app.application.cascade.cascadeLink import EmptyLink, Link
from app.application.cascade.contextResolver import extend
from app.dataModel.cascade.cascadeSpec import Cascade, ChannelKind, DefaultPolicy, ScopeAxis
from app.dataModel.cascade.runtimeContext import CascadeRuntimeContext, ResolvedCascadeState, freeze_resolved_context
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as WaterScope
from app.dataModel.hydrology.generation.generationContext import (
    ResolvedWaterGenerationContext, WaterGenerationContext,
)
from app.dataModel.hydrology.generation.waterGenerationSettings import BodyWaterGenerationSettings
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.validation.immutableValue import validate_immutable


class OtherScope(ScopeAxis):
    ROOT = "root"
    CHILD = "child"


AMOUNT = Cascade("amount", DefaultPolicy.NONE_IS_ERROR, OtherScope, input_types=((ChannelKind.VALUE, int),))
PAYLOAD = Cascade("payload", DefaultPolicy.NONE_IS_ERROR, OtherScope, input_types=((ChannelKind.VALUE, list),))


class OtherRuntime(CascadeRuntimeContext[OtherScope]):
    amount: Annotated[int | None, AMOUNT] = None


class OtherResolved(ResolvedCascadeState[OtherScope], frozen=True):
    amount: StrictInt


class MutableRuntime(CascadeRuntimeContext[OtherScope]):
    payload: Annotated[object, PAYLOAD]


class MutableResult(ResolvedCascadeState[OtherScope], frozen=True):
    payload: object


def water_context():
    ctx = extend(WaterGenerationContext.root(object()), EmptyLink(WaterScope.WORLD))
    ctx = extend(ctx, EmptyLink(WaterScope.CATEGORY))
    return extend(ctx, Link(WaterScope.WATER_BODY,
        BodyWaterGenerationSettings(water_fraction=0.0, autoresolve=False, strategy=Strategy.PLATE)))


class ResolvedContextTests(TestCase):
    def test_water_values_are_required_preserve_zero_false_and_roundtrip(self):
        ctx = water_context()
        result = freeze_resolved_context(ctx, ResolvedWaterGenerationContext)
        self.assertIsInstance(result, ResolvedWaterGenerationContext)
        self.assertEqual(result.level, ctx.level)
        self.assertEqual((result.water_fraction, result.autoresolve, result.strategy), (0.0, False, Strategy.PLATE))
        self.assertEqual(result.provenance, tuple(sorted(ctx.provenance.items())))
        self.assertTrue(all(field.is_required() for field in type(result).model_fields.values()))
        self.assertEqual(type(result).model_validate_json(result.model_dump_json()), result)
        validate_immutable(result)
        self.assertIs(cache_validate_immutable, validate_immutable)

    def test_private_world_links_defaults_and_runtime_metadata_are_not_transferred(self):
        ctx = water_context()
        original_world = ctx._world
        original_links = ctx._links
        result = freeze_resolved_context(ctx, ResolvedWaterGenerationContext)
        self.assertEqual(set(vars(result)), set(type(result).model_fields))
        self.assertFalse(type(result).__private_attributes__)
        for name in type(ctx).__private_attributes__:
            self.assertFalse(hasattr(result, name), name)
        self.assertIs(ctx._world, original_world)
        self.assertIs(ctx._links, original_links)
        self.assertTrue(ctx._default_sources)
        for field in type(result).model_fields.values():
            self.assertFalse(any(isinstance(meta, Cascade) for meta in field.metadata))

    def test_freeze_does_not_resolve_and_does_not_read_world(self):
        class UnreadableWorld:
            def __getattribute__(self, name):
                raise AssertionError("freeze must not read world")

        ctx = water_context()
        ctx._world = UnreadableWorld()
        with patch("app.application.cascade.contextResolver.extend", side_effect=AssertionError("resolve called")), \
             patch("app.application.policy.policyResolver.PolicyResolver.resolve", side_effect=AssertionError("policy called")):
            result = freeze_resolved_context(ctx, ResolvedWaterGenerationContext)
        self.assertEqual(result.strategy, ctx.strategy)

    def test_results_do_not_share_mutable_provenance_with_runtime_or_siblings(self):
        ctx = water_context()
        first = freeze_resolved_context(ctx, ResolvedWaterGenerationContext)
        second = freeze_resolved_context(ctx, ResolvedWaterGenerationContext)
        expected = first.provenance
        ctx.provenance.clear()
        self.assertEqual(first.provenance, expected)
        self.assertEqual(second.provenance, expected)
        with self.assertRaises(ValueError):
            first.water_fraction = 0.5
        with self.assertRaises(TypeError):
            first.provenance[0] = ("changed", (WaterScope.ROOT, "changed"))

    def test_partial_or_forged_runtime_is_not_completed_with_defaults(self):
        with self.assertRaises(ValueError):
            freeze_resolved_context(WaterGenerationContext.root(object()), ResolvedWaterGenerationContext)
        good = water_context()
        for updates in ({"water_fraction": None}, {"autoresolve": 1}, {"strategy": "plate"},
                        {"provenance": {}}, {"provenance": good.provenance | {"extra": (WaterScope.ROOT, "extra")}},
                        {"provenance": good.provenance | {"strategy": (OtherScope.ROOT, "source")}}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                freeze_resolved_context(good.model_copy(update=updates), ResolvedWaterGenerationContext)
        del good.__dict__["strategy"]
        with self.assertRaises(ValueError):
            freeze_resolved_context(good, ResolvedWaterGenerationContext)

    def test_same_generic_boundary_serves_another_domain_axis(self):
        ctx = OtherRuntime(level=OtherScope.CHILD, amount=42,
            provenance={"amount": (OtherScope.ROOT, "other.amount")})
        result = freeze_resolved_context(ctx, OtherResolved)
        self.assertEqual(result.amount, 42)
        self.assertIs(result.level, OtherScope.CHILD)
        validate_immutable(result)
        for source, target in ((ctx, ResolvedWaterGenerationContext), (water_context(), OtherResolved)):
            with self.assertRaises(ValueError):
                freeze_resolved_context(source, target)

    def test_schema_defaults_private_state_computed_fields_and_parameter_drift_are_rejected(self):
        class Defaulted(OtherResolved, frozen=True):
            amount: StrictInt = 9

        class Private(OtherResolved, frozen=True):
            _world: object = PrivateAttr(default=None)

        class Computed(OtherResolved, frozen=True):
            @computed_field
            @property
            def derived(self) -> int:
                raise AssertionError("computed field must not execute")

        class Additional(OtherResolved, frozen=True):
            additional: int

        class Missing(ResolvedCascadeState[OtherScope], frozen=True):
            pass

        class Unfrozen(OtherResolved, frozen=False):
            pass

        ctx = OtherRuntime(level=OtherScope.ROOT, amount=42, provenance={"amount": (OtherScope.ROOT, "source")})
        for target in (Defaulted, Private, Computed, Additional, Missing, Unfrozen):
            with self.subTest(target=target), self.assertRaises(ValueError):
                freeze_resolved_context(ctx, target)

    def test_mutable_or_opaque_payload_is_rejected_by_existing_immutable_validator(self):
        for value in (["mutable"], {"mutable": 1}, object()):
            ctx = MutableRuntime(level=OtherScope.ROOT, payload=value,
                provenance={"payload": (OtherScope.ROOT, "source")})
            with self.subTest(value=value), self.assertRaises(ValueError):
                freeze_resolved_context(ctx, MutableResult)
        ctx = MutableRuntime(level=OtherScope.ROOT, payload=("immutable",),
            provenance={"payload": (OtherScope.ROOT, "source")})
        self.assertEqual(freeze_resolved_context(ctx, MutableResult).payload, ("immutable",))

    def test_direct_result_revalidates_canonical_complete_provenance(self):
        good = freeze_resolved_context(water_context(), ResolvedWaterGenerationContext)
        for provenance in (tuple(reversed(good.provenance)), good.provenance + (good.provenance[0],), (),
                           tuple((name, (scope, "")) for name, (scope, _) in good.provenance)):
            with self.subTest(provenance=provenance), self.assertRaises(ValueError):
                ResolvedWaterGenerationContext.model_validate(good.model_copy(update={"provenance": provenance}))

    def test_nested_private_state_cannot_bypass_the_shared_immutable_check(self):
        class Nested(BaseModel, frozen=True):
            model_config = ConfigDict(frozen=True, extra="forbid")
            _hidden: object = PrivateAttr(default=None)

        for value in (object(), {}, [], {"world": object()}):
            nested = Nested()
            nested._hidden = value
            ctx = MutableRuntime(level=OtherScope.ROOT, payload=nested,
                provenance={"payload": (OtherScope.ROOT, "source")})
            with self.subTest(value=value), self.assertRaises(ValueError):
                freeze_resolved_context(ctx, MutableResult)
            with self.assertRaises(ValueError):
                cache_validate_immutable(nested)
        nested = Nested()
        nested._hidden = nested
        with self.assertRaises(ValueError):
            validate_immutable(nested)
        nested._hidden = ("immutable",)
        validate_immutable(nested)
