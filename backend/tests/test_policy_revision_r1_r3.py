"""Regression checks for E6-R1–R3: patch presence and safe error boundaries."""
import unittest
from types import SimpleNamespace

from pydantic import BaseModel, Field, field_validator

from app.application.jsonValidation.facade import normalize_world, merge_world_patch
from app.application.jsonValidation.resolve import ResolveContext, resolve_patch, resolve_result, UnresolvedModelError
from app.application.jsonValidation.types import ImportValidationError
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.terrainMasks.hillPolicy import HillPolicy
from app.dataModel.terrainMasks.hillShape import HillShape
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService, GenerationError


class PolicyRevisionTests(unittest.TestCase):
    def test_world_star_patch_keeps_authored_fields_until_merged_validation(self):
        existing = {"terrain_masks": {"default_mountains": {"default_form": {
            "form_type": "star", "rays": 5, "inner_ratio": 0.45}}}}
        changes = {"terrain_masks": {"default_mountains": {"default_form": {"rays": 7}}}}
        patch = normalize_world(changes, partial=True)
        self.assertEqual(patch, changes)
        full = normalize_world(merge_world_patch(existing, patch))
        form = full["terrain_masks"]["default_mountains"]["default_form"]
        self.assertEqual(form, {"form_type": "star", "rays": 7, "inner_ratio": 0.45})
        invalid = {"terrain_masks": {"default_mountains": {"default_form": {"rays": 1}}}}
        with self.assertRaises(ImportValidationError):
            normalize_world(merge_world_patch(existing, normalize_world(invalid, partial=True)))

    def test_explicit_union_branches_do_not_insert_defaults(self):
        for form in ({"form_type": "by_sides", "side_count": 7},
                     {"form_type": "star", "rays": 7},
                     {"form_type": "peak", "side_count": 4},
                     {"form_type": "plateau", "hat_fraction": 0.6}):
            with self.subTest(form=form):
                raw = {"default_mountains": {"default_form": form}}
                self.assertEqual(resolve_patch(WorldTerrainMasks, raw, ctx=ResolveContext(validate_only=True)), raw)
        for form in ({"form_type": "star", "rays": 1},
                     {"form_type": "plateau", "hat_fraction": 2},
                     {"form_type": "peak", "side_count": 1},
                     {"form_type": "by_sides", "side_count": 1},
                     {"form_type": "unknown"}):
            with self.subTest(form=form), self.assertRaises(UnresolvedModelError):
                resolve_patch(WorldTerrainMasks, {"default_mountains": {"default_form": form}},
                              ctx=ResolveContext(validate_only=True))

    def test_nested_before_validator_and_alias_are_retained(self):
        class Child(BaseModel):
            amount: int = Field(default=3, ge=0, alias="wire_amount")
        class Parent(BaseModel):
            child: Child
            @field_validator("child", mode="before")
            @classmethod
            def legacy(cls, value):
                if isinstance(value, dict) and "legacy_amount" in value:
                    return {"wire_amount": value["legacy_amount"]}
                return value
        self.assertEqual(resolve_patch(Parent, {"child": {"legacy_amount": 7}},
            ctx=ResolveContext(validate_only=True)), {"child": {"amount": 7}})
        self.assertEqual(resolve_patch(Parent, {"child": {}},
            ctx=ResolveContext(validate_only=True)), {"child": {}})
        with self.assertRaises(UnresolvedModelError):
            resolve_patch(Parent, {"child": {"legacy_amount": -1}}, ctx=ResolveContext(validate_only=True))

    def test_untagged_union_preserves_authored_alternative(self):
        from app.dataModel.locations.transitions.transition import Transition
        raw = {"type_params": {"staircase_type": "straight"}}
        self.assertEqual(resolve_patch(Transition, raw, ctx=ResolveContext(validate_only=True)), raw)

    def test_invalid_rooms_returns_report_and_runtime_generation_error(self):
        for rooms in (None, 1, False):
            with self.subTest(rooms=rooms):
                raw = {"system_name": "7c3a4d5e-6f7a-4b8c-8d9e-1f2a3b4c5d6e",
                       "display_name": "Review", "levels": [{"rooms": rooms}]}
                result = resolve_result(StructureTemplate, raw, ctx=ResolveContext(validate_only=True))
                self.assertFalse(result.resolved)
                self.assertIn("levels[0]", result.issues[0].message)
                template = SimpleNamespace(system_name=raw["system_name"], levels=raw["levels"])
                with self.assertRaisesRegex(GenerationError, r"levels\[0\]"):
                    StructureGeneratorService._resolve_levels(template, "building-review")

    def test_hill_null_rejected_in_full_and_patch_with_path(self):
        self.assertFalse(resolve_result(HillPolicy, {"shapes": None},
                                       ctx=ResolveContext(validate_only=True)).resolved)
        raw = {"terrain_masks": {"default_forests": {"hills": {"shapes": None}}}}
        for partial in (False, True):
            with self.subTest(partial=partial), self.assertRaises(ImportValidationError) as caught:
                normalize_world(raw, partial=partial)
            self.assertTrue(any(i.path == ("terrain_masks", "default_forests", "hills", "shapes")
                                for i in caught.exception.errors))

    def test_hill_missing_empty_weights_and_invalid_tokens(self):
        shape = next(iter(HillShape)).value
        for raw, expected in (({}, ()), ({"shapes": []}, ()),
                              ({"shapes": [shape, shape]}, (HillShape(shape), HillShape(shape)))):
            result = resolve_result(HillPolicy, raw, ctx=ResolveContext(validate_only=True))
            self.assertTrue(result.resolved)
            self.assertEqual(result.value.shapes, expected)
        for raw in ({"shapes": [shape, "unknown"]}, {"shapes": False}):
            self.assertFalse(resolve_result(HillPolicy, raw, ctx=ResolveContext(validate_only=True)).resolved)
            with self.assertRaises(UnresolvedModelError):
                resolve_patch(HillPolicy, raw, ctx=ResolveContext(validate_only=True))

