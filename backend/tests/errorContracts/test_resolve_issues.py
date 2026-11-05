"""jsonValidation J2: ResolveContext.location and Pydantic errors() translation (error-contracts-1)."""

import unittest
from enum import StrEnum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, RootModel, field_validator
from pydantic_core import PydanticCustomError

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.resolve import (
    ResolveContext, StrictFieldError, UnresolvedModelError, reject_unresolved, report_issues, resolve_model, resolve_patch,
)
from app.application.jsonValidation.types import (
    ImportValidationError, ImportValidationReport, import_validation_http_detail,
)
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class Shore(StrEnum):
    SAND = "sand"


class Bank(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shore: Shore
    width_m: int = Field(alias="width")


class Lake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    banks: list[Bank] = []
    depth: int = 1

    @field_validator("depth")
    @classmethod
    def _custom(cls, value: int) -> int:
        if value > 100:
            raise PydanticCustomError("DEPTH_CONFLICT", "too deep")
        return value


class Lakes(RootModel[list[Lake]]):
    pass


class Sampling(BaseModel):
    step_fine: int = Field(gt=0, validation_alias=AliasChoices("sample_step_fine", "sample_step_m"))


class ProbeCode(StrEnum):
    BROKEN = "broken"


class MutableProbeError(FieldPathError[ProbeCode]):
    data: list[str]


def _issues(call) -> list:
    try:
        call()
    except UnresolvedModelError as exc:
        return exc.issues
    raise AssertionError("expected UnresolvedModelError")


class ResolveIssuesTests(unittest.TestCase):
    def ctx(self) -> ResolveContext:
        return ResolveContext(location=WireLocation(parts=("hydrology", "lakes")), validate_only=True)

    def test_reject_reports_one_shot_iterable(self) -> None:
        ctx = self.ctx()
        issue = WireShapeIssue(code=JsonValidationCode.BUNDLE_INVALID, location=ctx.location, message="bad")
        self.assertEqual(_issues(lambda: reject_unresolved(ctx, iter([issue]))), [issue])
        self.assertEqual(ctx.errors, [issue])

    def test_removed_field_keeps_world_location_through_facade(self) -> None:
        ctx = ResolveContext.for_import(validate_only=True).child("world")
        for partial in (False, True):
            with self.subTest(partial=partial), self.assertRaises(ImportValidationError) as caught:
                normalize_world({"map_cell_size_m": None}, partial=partial, ctx=ctx)
            detail = import_validation_http_detail(caught.exception)
            self.assertEqual([item["loc"] for item in detail], [["world", "map_cell_size_m"]])
            self.assertEqual(detail[0]["code"], "REMOVED_FROM_WIRE")

    def test_child_extends_location(self) -> None:
        self.assertEqual(self.ctx().child(3).location.parts, ("hydrology", "lakes", 3))

    def test_field_errors_become_json_field_errors(self) -> None:
        ctx = self.ctx()
        issues = _issues(lambda: resolve_model(Lake, {"banks": [{"shore": "mud"}], "depth": 500}, ctx=ctx))
        self.assertTrue(all(isinstance(issue, JsonFieldError) for issue in issues))
        self.assertEqual(ctx.errors, issues)
        by_code = {(issue.code, issue.pydantic_type): issue for issue in issues}
        self.assertEqual(set(by_code), {
            (JsonValidationCode.UNKNOWN_ENUM, None),
            (JsonValidationCode.SCHEMA_VIOLATION, "missing"),
            (JsonValidationCode.VALIDATION_ERROR, None),
        })
        detail = import_validation_http_detail(ImportValidationError(issues))
        actual = {(tuple(item["loc"]), item["code"]) for item in detail}  # type: ignore[arg-type]
        self.assertEqual(actual, {
            (("hydrology", "lakes", "banks", 0, "shore"), "UNKNOWN_ENUM"),
            (("hydrology", "lakes", "banks", 0, "width"), "missing"),
            (("hydrology", "lakes", "depth"), "VALIDATION_ERROR"),
        })

    def test_undeclared_location_is_wire_shape_issue(self) -> None:
        (issue,) = _issues(lambda: resolve_model(Lake, {"rogue": 1}, ctx=self.ctx()))
        self.assertIsInstance(issue, WireShapeIssue)
        self.assertEqual(issue.location.parts, ("hydrology", "lakes", "rogue"))
        self.assertEqual(issue.pydantic_type, "extra_forbidden")
        detail = import_validation_http_detail(ImportValidationError([issue]))
        self.assertEqual(detail[0]["code"], "extra_forbidden")

    def test_root_model_location_skips_root(self) -> None:
        (issue,) = _issues(lambda: resolve_model(Lakes, [{"depth": "x"}], ctx=self.ctx()))
        self.assertIsInstance(issue, JsonFieldError)
        detail = import_validation_http_detail(ImportValidationError([issue]))
        self.assertEqual(detail[0]["loc"], ["hydrology", "lakes", 0, "depth"])

    def test_patch_shape_and_field_errors(self) -> None:
        (shape,) = _issues(lambda: resolve_patch(Lake, [], ctx=self.ctx()))  # type: ignore[arg-type]
        self.assertEqual((type(shape), shape.code), (WireShapeIssue, JsonValidationCode.EXPECTED_OBJECT))
        (field,) = _issues(lambda: resolve_patch(Lake, {"depth": "x"}, ctx=self.ctx()))
        self.assertIsInstance(field, JsonFieldError)
        self.assertEqual(field.pydantic_type, "int_parsing")

    def test_report_and_strict_error_admit_only_import_issues(self) -> None:
        with self.assertRaises(Exception):
            report_issues(self.ctx(), [{"code": "UNKNOWN_ENUM"}])  # type: ignore[list-item]
        issue = WireShapeIssue(code=JsonValidationCode.BUNDLE_INVALID, location=WireLocation(), message="bad")
        self.assertEqual(str(StrictFieldError(issue)), "bad")
        self.assertIs(StrictFieldError(issue).issue.code, JsonValidationCode.BUNDLE_INVALID)
        with self.assertRaises(Exception):
            WireShapeIssue(code=JsonValidationCode.SCHEMA_VIOLATION, location=WireLocation(), message="x")


class ReviewRegressionTests(unittest.TestCase):
    def test_patch_prioritizes_alias_over_python_name(self):
        class Amount(BaseModel):
            amount: int = Field(alias="wire_amount", ge=0)

        ctx = ResolveContext.for_import(validate_only=True)
        data = {"wire_amount": -1, "amount": 2}
        for resolve in (resolve_model, resolve_patch):
            with self.subTest(resolve=resolve.__name__):
                issue, = _issues(lambda: resolve(Amount, data, ctx=ctx))
                detail, = import_validation_http_detail(ImportValidationError([issue]))
                self.assertEqual((detail["loc"], detail["code"]), (["wire_amount"], "greater_than_equal"))
        self.assertEqual(resolve_patch(Amount, {}, ctx=ctx), {})
        self.assertEqual(resolve_patch(Amount, {"wire_amount": 1, "amount": 2}, ctx=ctx), {"amount": 1})

    def test_patch_keeps_climate_alias_choice_in_error_location(self):
        from app.dataModel.worldPack.wire.climateFieldWire import ClimateFieldWire

        ctx = ResolveContext.for_import(validate_only=True)
        issue, = _issues(lambda: resolve_patch(ClimateFieldWire, {"sample_step_m": 0}, ctx=ctx))
        detail, = import_validation_http_detail(ImportValidationError([issue]))
        self.assertEqual((detail["loc"], detail["code"]), (["sample_step_m"], "greater_than_equal"))
        self.assertEqual(resolve_patch(ClimateFieldWire, {"sample_step_m": 2}, ctx=ctx), {"sample_step_fine": 2})

    def test_patch_respects_models_that_disable_validation_aliases(self):
        class Amount(BaseModel):
            model_config = ConfigDict(validate_by_alias=False, validate_by_name=True)
            amount: int = Field(alias="wire_amount")

        raw = {"wire_amount": -1, "amount": 2}
        ctx = ResolveContext.for_import(validate_only=True)
        self.assertEqual(resolve_patch(Amount, raw, ctx=ctx), resolve_model(Amount, raw, ctx=ctx).model_dump())

    def test_http_loc_keeps_the_alias_choice_actually_used(self) -> None:
        for key in ("sample_step_fine", "sample_step_m"):
            with self.subTest(key=key):
                (issue,) = _issues(lambda: resolve_model(Sampling, {key: 0}, ctx=ResolveContext(validate_only=True)))
                self.assertIsInstance(issue, JsonFieldError)
                self.assertEqual(issue.path.segments[0].name, "step_fine")  # type: ignore[union-attr]
                detail = import_validation_http_detail(ImportValidationError([issue]))
                self.assertEqual(detail[0]["loc"], [key])

    def test_function_local_model_formats_without_module_lookup(self) -> None:
        class Local(BaseModel):
            depth: int

        (issue,) = _issues(lambda: resolve_model(Local, {"depth": "x"}, ctx=ResolveContext(validate_only=True)))
        self.assertEqual(str(ImportValidationError([issue])), "depth: Input should be a valid integer, unable to parse string as an integer")

    def test_published_report_rejects_mutable_issue_state(self) -> None:
        path = CheckedPath.from_pydantic_loc(Lake, ("depth",))
        assert path is not None
        issue = MutableProbeError(code=ProbeCode.BROKEN, path=path, message="m", data=["a"])
        with self.assertRaises(ValueError):
            ImportValidationReport((issue,))
        with self.assertRaises(ValueError):
            ImportValidationError([issue])


if __name__ == "__main__":
    unittest.main()
