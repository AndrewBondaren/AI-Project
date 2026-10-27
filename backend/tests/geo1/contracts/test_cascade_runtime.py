"""G1: independent axes and snapshots through the existing cascade engine."""

from typing import Annotated
from unittest import TestCase
from unittest.mock import patch

from pydantic import BaseModel, Field

from app.application.cascade.cascadeLink import EmptyLink, Link
from app.application.cascade.contextResolver import extend, scope_sequence
from app.dataModel.cascade.cascadeSpec import (
    Cascade, CascadeChannel, CascadeDefault, CascadeLink, ChannelKind, DefaultPolicy, FieldRef,
)
from app.dataModel.cascade.cascadeVerify import verify_cascade_contract
from app.dataModel.cascade.runtimeContext import CascadeRuntimeContext
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory, WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.context.scopeLevel import ScopeLevel


class ProbeDefaults(BaseModel):
    flag: bool = False
    fraction: float = 0.6
    payload: list[str] = Field(default_factory=list)


FLAG = Cascade("flag", DefaultPolicy.CANONICAL_DEFAULT, Scope,
    default_source=CascadeDefault(FieldRef(lambda: ProbeDefaults, lambda d: d.flag)),
    input_types=((ChannelKind.VALUE, bool),))
FRACTION = Cascade("fraction", DefaultPolicy.CANONICAL_DEFAULT, Scope,
    default_source=CascadeDefault(FieldRef(lambda: ProbeDefaults, lambda d: d.fraction)),
    input_types=((ChannelKind.VALUE, float),))
PAYLOAD = Cascade("payload", DefaultPolicy.CANONICAL_DEFAULT, Scope,
    default_source=CascadeDefault(FieldRef(lambda: ProbeDefaults, lambda d: d.payload)),
    input_types=((ChannelKind.VALUE, list),))

FLAG_REF = FieldRef(lambda: ProbeSource, lambda s: s.flag)
FRACTION_REF = FieldRef(lambda: ProbeSource, lambda s: s.fraction)
PAYLOAD_REF = FieldRef(lambda: ProbeSource, lambda s: s.payload)


class ProbeSource(BaseModel):
    flag: Annotated[bool | None,
        CascadeChannel(FLAG, Scope.WORLD),
        CascadeChannel(FLAG, Scope.CATEGORY, below=CascadeLink(FLAG_REF, Scope.WORLD)),
        CascadeChannel(FLAG, Scope.WATER_BODY, below=CascadeLink(FLAG_REF, Scope.CATEGORY))] = None
    fraction: Annotated[float | None,
        CascadeChannel(FRACTION, Scope.WORLD),
        CascadeChannel(FRACTION, Scope.CATEGORY, below=CascadeLink(FRACTION_REF, Scope.WORLD)),
        CascadeChannel(FRACTION, Scope.WATER_BODY, below=CascadeLink(FRACTION_REF, Scope.CATEGORY))] = None
    payload: Annotated[list[str] | None,
        CascadeChannel(PAYLOAD, Scope.WORLD),
        CascadeChannel(PAYLOAD, Scope.CATEGORY, below=CascadeLink(PAYLOAD_REF, Scope.WORLD)),
        CascadeChannel(PAYLOAD, Scope.WATER_BODY, below=CascadeLink(PAYLOAD_REF, Scope.CATEGORY))] = None


class ProbeWaterContext(WaterGenerationContext):
    flag: Annotated[bool | None, FLAG] = None
    fraction: Annotated[float | None, FRACTION] = None
    payload: Annotated[list[str] | None, PAYLOAD] = None


def root(defaults=None):
    return ProbeWaterContext.root(object(), default_sources=(defaults or ProbeDefaults(),))


class CascadeRuntimeTests(TestCase):
    def test_water_root_is_empty_and_location_api_is_preserved(self):
        world = object()
        water = WaterGenerationContext.root(world)
        location = LocationContext.root(world)
        self.assertIs(water.level, Scope.ROOT)
        self.assertIs(location.level, ScopeLevel.WORLD)
        for context in (water, location):
            self.assertIsInstance(context, CascadeRuntimeContext)
            self.assertIs(context._world, world)
            self.assertFalse(context._links)
            self.assertFalse(context._node_results)
            self.assertFalse(context.provenance)
        self.assertEqual({c.value for c in WaterGenerationCategory}, {"sea", "ocean", "lake"})

    def test_graph_verifier_accepts_bool_float_and_declared_world_channel(self):
        verify_cascade_contract(ProbeWaterContext)
        self.assertEqual(scope_sequence(root()), (Scope.ROOT, Scope.WORLD, Scope.CATEGORY, Scope.WATER_BODY))

    def test_explicit_zero_false_and_nullable_inheritance(self):
        world = extend(root(), Link(Scope.WORLD, ProbeSource(flag=True, fraction=0.7)))
        category = extend(world, EmptyLink(Scope.CATEGORY))
        body = extend(category, Link(Scope.WATER_BODY, ProbeSource(flag=False, fraction=0.0)))
        inherited = extend(category, EmptyLink(Scope.WATER_BODY))
        self.assertIs(type(body), ProbeWaterContext)
        self.assertFalse(body.flag)
        self.assertEqual(body.fraction, 0.0)
        self.assertEqual((inherited.flag, inherited.fraction), (True, 0.7))
        self.assertEqual(body.provenance["fraction"], (Scope.WATER_BODY, "ProbeSource.fraction"))
        self.assertEqual(inherited.provenance["flag"], (Scope.WORLD, "ProbeSource.flag"))

    def test_value_channels_do_not_call_materialization_or_fold(self):
        with patch("app.application.cascade.contextResolver._MATERIALIZE", {}), \
             patch("app.application.cascade.contextResolver._FOLDS", {}):
            world = extend(root(), Link(Scope.WORLD, ProbeSource(flag=False, fraction=0.0)))
            result = extend(extend(world, EmptyLink(Scope.CATEGORY)), EmptyLink(Scope.WATER_BODY))
        self.assertEqual((result.flag, result.fraction), (False, 0.0))

    def test_category_and_body_overrides_do_not_leak_into_siblings(self):
        world = extend(root(), Link(Scope.WORLD, ProbeSource(flag=True, fraction=0.7)))
        sea = extend(world, Link(Scope.CATEGORY, ProbeSource(fraction=0.2)))
        lake = extend(world, EmptyLink(Scope.CATEGORY))
        first = extend(sea, Link(Scope.WATER_BODY, ProbeSource(fraction=0.1)))
        sibling = extend(sea, EmptyLink(Scope.WATER_BODY))
        self.assertEqual((world.fraction, sea.fraction, lake.fraction, first.fraction, sibling.fraction),
                         (0.7, 0.2, 0.7, 0.1, 0.2))
        first.provenance.clear()
        self.assertTrue(sibling.provenance)
        self.assertTrue(sea.provenance)

    def test_sources_and_nested_node_results_are_independent_snapshots(self):
        source = ProbeSource(payload=["original"])
        world = extend(root(), Link(Scope.WORLD, source))
        source.payload.append("caller-mutated")
        category = extend(world, EmptyLink(Scope.CATEGORY))
        first = extend(category, EmptyLink(Scope.WATER_BODY))
        sibling = extend(category, EmptyLink(Scope.WATER_BODY))
        first._links[Scope.WORLD][0].payload.append("changed-link")
        first.payload.append("changed-result")
        self.assertEqual(sibling.payload, ["original"])
        self.assertEqual(category.payload, ["original"])
        self.assertEqual(world._links[Scope.WORLD][0].payload, ["original"])
        self.assertIsNot(first._node_results, sibling._node_results)

    def test_defaults_are_snapshotted_without_evaluating_them_at_root(self):
        defaults = ProbeDefaults(fraction=0.4, payload=["captured"])
        original = root(defaults)
        defaults.fraction = 0.9
        defaults.payload.append("caller-change")
        world = extend(original, EmptyLink(Scope.WORLD))
        category = extend(world, EmptyLink(Scope.CATEGORY))
        category._default_sources[0].payload.append("child-change")
        self.assertEqual(world.fraction, 0.4)
        self.assertEqual(world._default_sources[0].payload, ["captured"])
        self.assertFalse(original.provenance)

    def test_wrong_axis_skipped_scopes_and_repeated_scopes_are_rejected(self):
        for link in (EmptyLink(ScopeLevel.WORLD), EmptyLink(Scope.WATER_BODY)):
            with self.assertRaises(ValueError):
                extend(root(), link)
        world = extend(root(), EmptyLink(Scope.WORLD))
        with self.assertRaises(ValueError):
            extend(world, EmptyLink(Scope.WORLD))
        world._scope_path = (Scope.ROOT, Scope.WORLD, ScopeLevel.WORLD)
        with self.assertRaisesRegex(ValueError, "foreign axis"):
            scope_sequence(world)

    def test_runtime_bindings_checked_for_each_concrete_context(self):
        invalid = Cascade("bad", DefaultPolicy.NONE_IS_ERROR, Scope, materialize="unbound")
        class BadContext(WaterGenerationContext):
            bad: Annotated[str | None, invalid] = None
        with self.assertRaisesRegex(ValueError, "no binding"):
            extend(BadContext.root(object()), EmptyLink(Scope.WORLD))

    def test_context_axis_is_checked_by_verifier_and_runtime(self):
        class WrongContext(LocationContext):
            flag: Annotated[bool | None, FLAG] = None
        with self.assertRaisesRegex(ValueError, "foreign axis"):
            verify_cascade_contract(WrongContext)
        with self.assertRaisesRegex(ValueError, "foreign axis"):
            scope_sequence(WrongContext.root(object()))

    def test_unrelated_broken_loaded_domains_do_not_poison_verification(self):
        unrelated = Cascade("other", DefaultPolicy.NONE_IS_ERROR, ScopeLevel)
        repeated = CascadeChannel(unrelated, ScopeLevel.SETTLEMENT)
        class UnrelatedBrokenSource(BaseModel):
            other: Annotated[str | None, repeated, repeated] = None
        with patch("app.dataModel.cascade.cascadeVerify._source_models", return_value={ProbeSource, UnrelatedBrokenSource}), \
             patch("app.dataModel.cascade.cascadeGraph._source_models", return_value={ProbeSource, UnrelatedBrokenSource}):
            verify_cascade_contract(ProbeWaterContext)
