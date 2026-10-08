"""The two policy pilots: schema constraints, patch intent and real cascade boundary."""
import unittest
from unittest.mock import patch

from pydantic import BaseModel, Field, RootModel, model_validator

from app.application.jsonValidation.resolve import (
    ResolveContext, ResolveMode, UnresolvedModelError, resolve_model, resolve_patch,
    resolve_result, resolve_root_list,
)
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.worldData.context.locationScope import empty_location_chain, room_context
from app.dataModel.annotationPolicy import DefaultWhenMissing, field_policy, WireFieldPolicy
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.structure.room.roomDef import RoomDef
from app.dataModel.terrainMasks.worldTerrainMasks import ForestsCategoryPolicy, WorldTerrainMasks
from tests.test_context_extend import _world, _room


class RuntimeWorldEditPolicyTests(unittest.TestCase):
    def test_missing_and_supplied_valid(self):
        for raw, expected in (({}, 45), ({"forest_min_rainfall": 60}, 60)):
            result = resolve_result(ForestsCategoryPolicy, raw)
            self.assertTrue(result.resolved)
            self.assertEqual(result.value.forest_min_rainfall, expected)

    def test_invalid_has_same_fact_and_no_value_in_both_contexts(self):
        for invalid in (-1, "abc", None):
            facts = []
            for mode in ResolveMode:
                ctx = ResolveContext(mode=mode, validate_only=mode == ResolveMode.IMPORT,
                                     path_prefix=("terrain_masks", "default_forests"))
                with patch("app.application.jsonValidation.resolve.logger") as log:
                    result = resolve_result(ForestsCategoryPolicy, {"forest_min_rainfall": invalid}, ctx=ctx)
                self.assertFalse(result.resolved)
                self.assertIsNone(result.value)
                self.assertEqual(len(ctx.errors), 1)
                self.assertEqual(log.warning.called, mode == ResolveMode.RUNTIME)
                facts.append(result.issues)
            self.assertEqual(facts[0], facts[1])
            self.assertEqual(facts[0][0].path, ("terrain_masks", "default_forests", "forest_min_rainfall"))

    def test_nested_parent_must_not_replace_invalid_child(self):
        raw = {"default_forests": {"forest_min_rainfall": -1}}
        with self.assertRaises(UnresolvedModelError):
            resolve_model(WorldTerrainMasks, raw)
        with self.assertRaises(ImportValidationError):
            normalize_world({"terrain_masks": raw})

    def test_patch_preserves_absence_nested(self):
        ctx = ResolveContext(mode=ResolveMode.IMPORT, partial=True)
        self.assertEqual(resolve_patch(ForestsCategoryPolicy, {}, ctx=ctx), {})
        self.assertEqual(resolve_patch(WorldTerrainMasks, {"default_forests": {}}, ctx=ctx), {"default_forests": {}})
        with self.assertRaises(UnresolvedModelError):
            resolve_patch(ForestsCategoryPolicy, {"forest_min_rainfall": None}, ctx=ctx)

    def test_alias_and_field_metadata(self):
        class Aliased(BaseModel):
            amount: DefaultWhenMissing[int] = Field(default=2, alias="wire_amount", ge=0)
        result = resolve_result(Aliased, {"wire_amount": -1})
        self.assertFalse(result.resolved)
        self.assertEqual(result.issues[0].code, "greater_than_equal")
        self.assertEqual(resolve_result(Aliased, {"wire_amount": 3}).value.amount, 3)

    def test_collection_never_returns_partial_registry(self):
        class Rows(RootModel[list[ForestsCategoryPolicy]]):
            pass
        with self.assertRaises(UnresolvedModelError):
            resolve_root_list(Rows, [{}, {"forest_min_rainfall": -1}], empty_factory=lambda: Rows([]), label="rows")

    def test_cascade_metadata_and_real_membership_boundary(self):
        self.assertEqual(field_policy(RoomDef.model_fields["economic_tier"].annotation), WireFieldPolicy.DEFAULT_WHEN_MISSING)
        world = _world()
        parent = empty_location_chain(world, ScopeLevel.BUILDING)
        for mode in ResolveMode:
            ctx = ResolveContext(mode=mode, validate_only=mode == ResolveMode.IMPORT, path_prefix=("rooms", "r1"))
            with patch("app.application.worldData.context.locationScope.extend") as extend:
                with self.assertRaises(UnresolvedModelError) as error:
                    room_context(world, parent, _room("unknown"), room_uid="r1", resolve_ctx=ctx)
                extend.assert_not_called()
            self.assertEqual(error.exception.issues[0].code, "REF_W_UNKNOWN")
            self.assertEqual(error.exception.issues[0].path, ("rooms", "r1", "economic_tier"))
        for value in (None, "t2"):
            result = room_context(world, parent, _room(value), room_uid="r1")
            self.assertEqual(result.economic_tier, parent.economic_tier if value is None else value)
        self.assertEqual(parent.level, ScopeLevel.BUILDING)

    def test_invalid_type_never_becomes_empty_cascade_link(self):
        raw = _room().model_dump(mode="json")
        raw["economic_tier"] = 123
        result = resolve_result(RoomDef, raw)
        self.assertFalse(result.resolved)
        self.assertEqual(result.issues[0].path, ("economic_tier",))

    def test_room_defaults_preserve_authored_presence(self):
        raw = _room().model_dump(mode="json", exclude_unset=True)
        raw.update(required=False, count_range=[1, 3])
        result = resolve_result(RoomDef, raw)
        self.assertTrue(result.resolved, result.issues)
        self.assertNotIn("count", result.value.model_fields_set)
        self.assertFalse(result.value.perimeter_required_explicitly_disabled)

    def test_unavailable_or_invalid_registry_never_supplies_canonical_tier(self):
        world = _world()
        parent = empty_location_chain(world, ScopeLevel.BUILDING)
        for registry in (None, "invalid", [{"system_tier": None}]):
            world.economic_tier_registry = registry
            with self.assertRaises(UnresolvedModelError) as error:
                room_context(world, parent, _room("t2"), room_uid="r1")
            self.assertEqual(error.exception.issues[0].code, "REF_W_UNAVAILABLE")

    def test_bad_parent_shape_cannot_hide_child_contract(self):
        for raw in (None, {"default_forests": "invalid"}):
            self.assertFalse(resolve_result(WorldTerrainMasks, raw).resolved)

    def test_report_is_shared_only_with_children(self):
        ctx = ResolveContext(mode=ResolveMode.IMPORT)
        resolve_result(ForestsCategoryPolicy, {"forest_min_rainfall": -1}, ctx=ctx.child("forest"))
        self.assertEqual(ctx.errors[0].path, ("forest", "forest_min_rainfall"))
        self.assertFalse(ResolveContext().errors)

    def test_model_invariant_never_produces_unchecked_success(self):
        class Bounds(BaseModel):
            lower: DefaultWhenMissing[int] = 0
            upper: DefaultWhenMissing[int] = 1

            @model_validator(mode="after")
            def ordered(self):
                if self.lower > self.upper:
                    raise ValueError("lower exceeds upper")
                return self

        ctx = ResolveContext.for_import(validate_only=True)
        patch = resolve_patch(Bounds, {"lower": 5}, ctx=ResolveContext(partial=True))
        self.assertEqual(patch, {"lower": 5})
        result = resolve_result(Bounds, {"upper": 1, **patch}, ctx=ctx)
        self.assertFalse(result.resolved)
        self.assertEqual(result.issues[0].path, ())


if __name__ == "__main__":
    unittest.main()
