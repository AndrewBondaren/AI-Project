"""G2-P: only present valid legacy flags migrate; canonical fields remain single-owner."""

from copy import deepcopy
from itertools import product
from unittest import TestCase

from pydantic import StrictBool, ValidationError

from app.application.cascade.cascadeLink import EmptyLink, Link
from app.application.cascade.contextResolver import extend
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, resolve_model, resolve_patch
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.legacySettings import normalize_lakes_generation, normalize_seas_generation
from app.dataModel.hydrology.generation.waterGenerationSettings import (
    CategoryWaterGenerationSettings, LakesGenerationFields, SeasGenerationFields, WorldWaterGenerationSettings,
)
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy

CASES = ((SeasGenerationFields, "autoresolve_coastal_sea", "sea_generation"),
         (SeasGenerationFields, "autoresolve_open_ocean", "ocean_generation"),
         (LakesGenerationFields, "autoresolve", "generation"))


class LegacyGenerationTests(TestCase):
    def test_absent_flags_never_materialize_legacy_true_defaults(self):
        self.assertEqual(normalize_seas_generation({}), {})
        self.assertEqual(normalize_lakes_generation({}), {})
        seas = SeasGenerationFields()
        lakes = LakesGenerationFields()
        self.assertIsNone(seas.sea_generation.autoresolve)
        self.assertIsNone(seas.ocean_generation.autoresolve)
        self.assertIsNone(lakes.generation.autoresolve)
        self.assertEqual(seas.model_dump(exclude_unset=True), {})
        self.assertEqual(lakes.model_dump(exclude_unset=True), {})

    def test_each_old_flag_migrates_false_and_true_without_mutating_input(self):
        for (model, old, target), flag in product(CASES, (False, True)):
            raw = {old: flag}
            before = deepcopy(raw)
            value = model.model_validate(raw)
            self.assertIs(getattr(value, target).autoresolve, flag)
            exported = value.model_dump(exclude_unset=True)
            self.assertEqual(exported, {target: {"autoresolve": flag}})
            self.assertEqual(raw, before)
            self.assertEqual(model.model_validate_json(value.model_dump_json(exclude_unset=True)), value)

    def test_equal_old_new_removes_old_and_preserves_other_fields(self):
        for (model, old, target), flag in product(CASES, (False, True)):
            raw = {old: flag, target: {"autoresolve": flag, "water_fraction": 0.0, "strategy": "plate"}}
            value = model.model_validate(raw)
            self.assertNotIn(old, value.model_dump())
            self.assertEqual(getattr(value, target).water_fraction, 0.0)
            self.assertEqual(getattr(value, target).strategy.value, "plate")

    def test_conflicting_old_new_and_explicit_new_null_are_errors(self):
        for (model, old, target), flag in product(CASES, (False, True)):
            for current in (not flag, None):
                with self.subTest(old=old, flag=flag, current=current), self.assertRaises(ValidationError) as caught:
                    model.model_validate({old: flag, target: {"autoresolve": current}})
                self.assertEqual(caught.exception.errors()[0]["type"], "GENERATION_SETTINGS_CONFLICT")

    def test_missing_and_null_new_leaf_are_distinct(self):
        for model, old, target in CASES:
            explicit = model.model_validate({target: {"autoresolve": None}})
            self.assertEqual(explicit.model_dump(exclude_unset=True), {target: {"autoresolve": None}})
            inherited = model.model_validate({target: {}})
            self.assertEqual(inherited.model_dump(exclude_unset=True), {target: {}})
            migrated = model.model_validate({old: False, target: {}})
            self.assertEqual(migrated.model_dump(exclude_unset=True), {target: {"autoresolve": False}})

    def test_invalid_legacy_and_new_types_are_not_coerced_to_equal(self):
        for model, old, target in CASES:
            for invalid in (None, 0, 1, "false", "true", [], {}):
                with self.subTest(old=old, invalid=invalid), self.assertRaises(ValidationError):
                    model.model_validate({old: invalid})
            for invalid in (0, 1, "false", "true"):
                with self.subTest(target=target, invalid=invalid), self.assertRaises(ValidationError):
                    model.model_validate({old: True, target: {"autoresolve": invalid}})

    def test_container_null_and_nonobject_are_not_replaced_with_empty(self):
        for model, old, target in CASES:
            for invalid in (None, [], False, "settings"):
                for with_old in (False, True):
                    raw = {target: invalid}
                    if with_old:
                        raw[old] = False
                    with self.assertRaises(ValidationError):
                        model.model_validate(raw)

    def test_typed_nested_source_retains_authored_presence(self):
        empty = CategoryWaterGenerationSettings(water_fraction=0.3)
        value = SeasGenerationFields.model_validate({"autoresolve_coastal_sea": False, "sea_generation": empty})
        self.assertEqual(value.sea_generation.model_dump(exclude_unset=True), {"water_fraction": 0.3, "autoresolve": False})
        self.assertEqual(empty.model_dump(exclude_unset=True), {"water_fraction": 0.3})
        forged = empty.model_copy(update={"autoresolve": 1})
        with self.assertRaises(ValidationError):
            SeasGenerationFields.model_validate({"autoresolve_coastal_sea": True, "sea_generation": forged})

    def test_normalizer_preserves_unrelated_payload_and_is_idempotent(self):
        for normalize, raw in ((normalize_seas_generation,
                {"enabled": False, "basin_depth": 9, "autoresolve_coastal_sea": False,
                 "ocean_generation": {"water_fraction": 0.5}}),
                (normalize_lakes_generation, {"enabled": True, "autoresolve": False, "bands": {"min": 1}})):
            before = deepcopy(raw)
            normalized = normalize(raw)
            self.assertEqual(normalize(normalized), normalized)
            self.assertEqual(raw, before)
            self.assertEqual(normalized["enabled"], raw["enabled"])

    def test_independent_sea_and_ocean_select_the_same_category_prototype(self):
        fields = SeasGenerationFields.model_validate({"autoresolve_coastal_sea": False, "autoresolve_open_ocean": True})
        world = extend(WaterGenerationContext.root(object()),
                       Link(Scope.WORLD, WorldWaterGenerationSettings(autoresolve=True)))
        sea = extend(world, Link(Scope.CATEGORY, fields.sea_generation))
        ocean = extend(world, Link(Scope.CATEGORY, fields.ocean_generation))
        self.assertIs(sea.autoresolve, False)
        self.assertIs(ocean.autoresolve, True)
        self.assertIs(extend(sea, EmptyLink(Scope.WATER_BODY)).autoresolve, False)
        self.assertEqual(sea.provenance["autoresolve"], (Scope.CATEGORY, "CategoryWaterGenerationSettings.autoresolve"))

    def test_lake_missing_and_new_null_inherit_world_while_false_overrides(self):
        world = extend(WaterGenerationContext.root(object()), Link(Scope.WORLD, WorldWaterGenerationSettings(autoresolve=True)))
        for raw, expected in (({}, True), ({"generation": {"autoresolve": None}}, True),
                              ({"autoresolve": False}, False), ({"generation": {"autoresolve": False}}, False)):
            fields = LakesGenerationFields.model_validate(raw)
            resolved = extend(world, Link(Scope.CATEGORY, fields.generation))
            self.assertIs(resolved.autoresolve, expected)

    def test_shared_wire_engine_uses_the_owning_before_validator(self):
        for model, old, target in CASES:
            ctx = ResolveContext(validate_only=True)
            value = resolve_model(model, {old: False}, ctx=ctx)
            self.assertIs(getattr(value, target).autoresolve, False)
            self.assertFalse(ctx.errors)
            with self.assertRaises(UnresolvedModelError):
                resolve_model(model, {old: True, target: {"autoresolve": False}}, ctx=ctx)
            self.assertEqual(ctx.errors[-1].code, "GENERATION_SETTINGS_CONFLICT")

    def test_patch_normalizes_only_supplied_values(self):
        for model, old, target in CASES:
            ctx = ResolveContext(validate_only=True)
            self.assertEqual(resolve_patch(model, {}, ctx=ctx), {})
            normalize = normalize_seas_generation if model is SeasGenerationFields else normalize_lakes_generation
            canonical = normalize({old: False})
            self.assertIsInstance(canonical, dict)
            self.assertEqual(resolve_patch(model, canonical, ctx=ctx), {target: {"autoresolve": False}})
            self.assertEqual(resolve_patch(model, {target: {"autoresolve": None}}, ctx=ctx), {target: {"autoresolve": None}})

    def test_future_owner_can_reuse_fields_without_a_second_copy(self):
        class SeaOwner(SeasGenerationFields):
            enabled: StrictBool = True
            basin_depth: int = 20
        value = SeaOwner.model_validate({"enabled": False, "basin_depth": 7, "autoresolve_open_ocean": False})
        self.assertFalse(value.enabled)
        self.assertEqual(value.basin_depth, 7)
        self.assertFalse(value.ocean_generation.autoresolve)
        self.assertNotIn("autoresolve_open_ocean", value.model_dump())

    def test_production_policies_and_rivers_retain_the_baseline(self):
        active = WorldHydrology()
        self.assertTrue(MaskCategoryPolicy().autoresolve)
        self.assertTrue(active.default_rivers.autoresolve)
        self.assertTrue(active.default_lakes.autoresolve)
        self.assertTrue(active.default_seas.autoresolve_coastal_sea)
        self.assertNotIn("generation", type(active.default_lakes).model_fields)
        self.assertNotIn("sea_generation", type(active.default_seas).model_fields)
