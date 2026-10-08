"""E6 field migration: real schemas, authored presence, patch validators and DB wire."""
import unittest
from dataclasses import dataclass
from enum import StrEnum
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, resolve_model, resolve_patch, resolve_result, resolve_root_list, resolve_root_dict
from app.application.jsonValidation.worldSlices import climate_zone_wire_from_raw, registry_map_to_list
from app.dataModel.annotationPolicy import DefaultWhenMissing, DefaultEnumWhenMissing, field_policy, WireFieldPolicy, wire_enum_class
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.dataModel.races.raceTemplateOutline import RaceTemplateOutline
from app.dataModel.perks.perkTemplateOutline import PerkTemplateOutline
from app.dataModel.worldScalarWire import scalar_wire_from_mapping
from app.db.mapper import json_col, json_list_col, from_row, to_row


class Choice(StrEnum):
    FIRST = "first"


class Child(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: DefaultWhenMissing[int] = Field(default=3, ge=0)


class Parent(BaseModel):
    child: DefaultWhenMissing[Child | None] = None
    choices: DefaultEnumWhenMissing[Choice] = Choice.FIRST
    rows: DefaultWhenMissing[list[Child]] = Field(default_factory=list)
    token: DefaultWhenMissing[str | list[str] | None] = None


class FieldMigrationTests(unittest.TestCase):
    def test_invalid_enum_and_collections_never_default_or_skip(self):
        for raw in ({"choices": "unknown"}, {"choices": None}, {"rows": [0]}, {"rows": [{"amount": -1}]}, {"rows": None}):
            facts = []
            for preview in (False, True):
                ctx = ResolveContext.for_import(validate_only=preview)
                with patch("app.application.jsonValidation.resolve.logger") as log:
                    result = resolve_result(Parent, raw, ctx=ctx)
                self.assertFalse(result.resolved, raw)
                self.assertEqual(log.warning.called, not preview)
                facts.append(result.issues)
            self.assertEqual(facts[0], facts[1])
        self.assertIs(resolve_model(Parent, {}).choices, Choice.FIRST)
        self.assertIs(wire_enum_class(Parent.model_fields["choices"].annotation), Choice)

    def test_valid_union_and_explicit_null_keep_presence(self):
        for token in (None, "square", ["square", "rectangle"]):
            value = resolve_model(Parent, {"token": token, "child": None})
            self.assertEqual(value.token, token)
            self.assertIn("child", value.model_fields_set)
            self.assertIn("token", value.model_fields_set)
            self.assertNotIn("choices", value.model_fields_set)

    def test_nullable_numeric_constraints_accept_null_and_reject_bad_number(self):
        info = MaterialRegistryEntry.model_fields
        base = dict(system_material="test", display_name="Test", material_category="solid")
        # Use a declared member, without duplicating the material category catalog.
        from app.dataModel.materials.enums.materialCategory import MaterialCategory
        base["material_category"] = next(iter(MaterialCategory)).value
        for name in ("hardness", "density", "viscosity", "structural_strength"):
            self.assertIsNone(resolve_model(MaterialRegistryEntry, {**base, name: None}).model_dump()[name])
            self.assertFalse(resolve_result(MaterialRegistryEntry, {**base, name: -1}).resolved)
            self.assertEqual(field_policy(info[name].annotation), WireFieldPolicy.DEFAULT_WHEN_MISSING)

    def test_patch_preserves_optional_nested_missing_and_explicit_null(self):
        ctx = ResolveContext(partial=True, validate_only=True)
        self.assertEqual(resolve_patch(Parent, {"child": {}}, ctx=ctx), {"child": {}})
        self.assertEqual(resolve_patch(Parent, {"child": None}, ctx=ctx), {"child": None})
        for raw in ({"child": {"amount": -1}}, {"child": "bad"}, {"rows": [{"amount": -1}]}):
            with self.assertRaises(UnresolvedModelError):
                resolve_patch(Parent, raw, ctx=ResolveContext(partial=True, validate_only=True))

    def test_patch_reuses_field_validator_and_forbid_extra(self):
        class WithValidator(BaseModel):
            model_config = ConfigDict(extra="forbid")
            code: DefaultWhenMissing[str] = Field(default="ok", validation_alias="wire_code")
            @field_validator("code", mode="before")
            @classmethod
            def alias(cls, value):
                if value == "legacy":
                    return "ok"
                if value != "ok":
                    raise ValueError("unknown code")
                return value
        ctx = ResolveContext(partial=True, validate_only=True)
        self.assertEqual(resolve_patch(WithValidator, {"wire_code": "legacy"}, ctx=ctx), {"code": "ok"})
        self.assertEqual(resolve_patch(WithValidator, {}, ctx=ctx), {})
        for raw in ({"code": "bad"}, {"typo": 1}):
            with self.assertRaises(UnresolvedModelError):
                resolve_patch(WithValidator, raw, ctx=ctx)

    def test_model_before_validator_is_not_bypassed(self):
        class Legacy(BaseModel):
            amount: DefaultWhenMissing[int] = 1
            @model_validator(mode="before")
            @classmethod
            def convert(cls, value):
                return {"amount": value["legacy_amount"]} if "legacy_amount" in value else value
        self.assertEqual(resolve_model(Legacy, {"legacy_amount": 7}).amount, 7)
        self.assertFalse(resolve_result(Legacy, {"legacy_amount": "invalid"}).resolved)

    def test_scalar_registry_does_not_stringify_invalid_rows(self):
        class Strings(RootModel[list[str]]):
            pass
        class Mapping(RootModel[dict[str, Child]]):
            pass
        for raw in (["ok", 123], False, 0, "", {}):
            with self.assertRaises(UnresolvedModelError):
                resolve_root_list(Strings, raw, empty_factory=lambda: Strings([]), label="strings")
        with self.assertRaises(UnresolvedModelError):
            resolve_root_dict(Mapping, {"good": {}, "bad": 1}, empty_factory=lambda: Mapping({}), label="mapping")

    def test_adapters_preserve_errors_and_missing_scalar_fields(self):
        self.assertEqual(climate_zone_wire_from_raw([{}, 0]), [{}, 0])
        self.assertEqual(registry_map_to_list({"good": {}, "bad": 0}, id_field="id"), [{"id": "good"}, 0])
        for value in (False, 0, ""):
            self.assertEqual(registry_map_to_list(value, id_field="id"), value)
        self.assertEqual(scalar_wire_from_mapping(frozenset({"a", "b"}), {"a": None}), {"a": None})

    def test_identity_autofill_does_not_repair_empty_strings(self):
        for cls in (RaceTemplateOutline, PerkTemplateOutline):
            self.assertTrue(resolve_model(cls, {}).template_uid)
            for field in ("template_uid", "system_name", "display_name"):
                self.assertFalse(resolve_result(cls, {field: ""}).resolved)

    def test_db_json_preserves_type_and_invalid_values_for_diagnostics(self):
        @dataclass
        class Row:
            entries: list = json_list_col()
            blob: dict = json_col(default_factory=dict)
        self.assertEqual(from_row(Row, {"entries": None, "blob": None}), Row())
        self.assertEqual(from_row(Row, {"entries": "{}", "blob": "{}"}), Row())
        for invalid in (False, 0, "invalid", [1]):
            value = Row(entries=invalid, blob=invalid)
            columns, values = to_row(value)
            self.assertEqual(from_row(Row, dict(zip(columns, values))), value)


if __name__ == "__main__":
    unittest.main()
