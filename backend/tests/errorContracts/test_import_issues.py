"""jsonValidation import issues and the 422 mapper (error-contracts-1 jsonValidation D1)."""

import unittest
from enum import StrEnum

from pydantic import BaseModel, Field, ValidationError

from app.application.jsonValidation.types import (
    ImportValidationError, ImportValidationReport, import_validation_http_detail,
)
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class Waypoint(BaseModel):
    uid: str


class River(BaseModel):
    from_wp: Waypoint = Field(alias="from")
    widths: tuple[int, ...] = ()


class OtherCode(StrEnum):
    BROKEN = "broken"


class OtherTypeError(FieldPathError[OtherCode]):
    pass


def _path(loc: tuple[str | int, ...]):
    path = CheckedPath.from_pydantic_loc(River, loc)
    assert path is not None
    return path


RIVERS = WireLocation(parts=("hydrology", "rivers", 2))


class JsonFieldErrorTests(unittest.TestCase):
    def test_pydantic_type_only_for_schema_violation(self) -> None:
        JsonFieldError(code=JsonValidationCode.SCHEMA_VIOLATION, path=_path(("widths", 0)), wire_path=("widths", 0), message="m",
                       location=RIVERS, pydantic_type="int_type")
        with self.assertRaises(ValidationError):
            JsonFieldError(code=JsonValidationCode.SCHEMA_VIOLATION, path=_path(("widths",)), wire_path=("widths",), message="m",
                           location=RIVERS)
        with self.assertRaises(ValidationError):
            JsonFieldError(code=JsonValidationCode.REF_W_UNKNOWN, path=_path(("widths",)), wire_path=("widths",), message="m",
                           location=RIVERS, pydantic_type="missing")
        with self.assertRaises(ValidationError):
            JsonFieldError(code=JsonValidationCode.SCHEMA_VIOLATION, path=_path(("widths",)), wire_path=("widths",), message="m",
                           location=RIVERS, pydantic_type="not_a_pydantic_type")  # pyright: ignore[reportArgumentType]

    def test_foreign_code_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            JsonFieldError(code=OtherCode.BROKEN, path=_path(("widths",)), wire_path=("widths",), message="m",  # pyright: ignore[reportArgumentType]
                           location=RIVERS)

    def test_wire_location(self) -> None:
        self.assertEqual(WireLocation().child("locations", "uid-1").parts, ("locations", "uid-1"))
        with self.assertRaises(ValidationError):
            WireLocation(parts=("rows", -1))
        with self.assertRaises(ValidationError):
            WireLocation(parts=(True,))


class ImportValidationErrorTests(unittest.TestCase):
    def test_carrier_admits_import_issues_and_rejects_others(self) -> None:
        field = JsonFieldError(code=JsonValidationCode.REF_W_UNKNOWN, path=_path(("from", "uid")), wire_path=("from", "uid"),
                               message="unknown", location=RIVERS, schema_id="SCH-HYDRO")
        shape = WireShapeIssue(code=JsonValidationCode.EXPECTED_LIST, location=WireLocation(parts=("states",)),
                               message="expected list")
        other = OtherTypeError(code=OtherCode.BROKEN, path=_path(("widths", 1)), message="broken")
        exc = ImportValidationError([field, shape, other])
        self.assertEqual([type(e) for e in exc.errors], [JsonFieldError, WireShapeIssue, OtherTypeError])
        self.assertEqual(str(exc), "hydrology.rivers.2.from.uid: unknown; states: expected list; widths.1: broken")
        for bad in ({"code": "EXPECTED_LIST"}, Waypoint(uid="x"),
                    shape.model_copy(update={"code": OtherCode.BROKEN})):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                ImportValidationError([bad])  # pyright: ignore[reportArgumentType]

    def test_http_detail_is_the_only_wire_projection(self) -> None:
        issues = (
            JsonFieldError(code=JsonValidationCode.SCHEMA_VIOLATION, path=_path(("from", "uid")), wire_path=("from", "uid"),
                           message="Field required", location=RIVERS, schema_id="SCH-HYDRO",
                           pydantic_type="missing"),
            JsonFieldError(code=JsonValidationCode.UNKNOWN_ENUM, path=_path(("widths", 0)), wire_path=("widths", 0), message="bad",
                           location=WireLocation()),
            WireShapeIssue(code=JsonValidationCode.BUNDLE_INVALID, location=WireLocation(), message="broken bundle"),
            OtherTypeError(code=OtherCode.BROKEN, path=_path(("widths", 1)), message="broken"),
        )
        self.assertEqual(import_validation_http_detail(ImportValidationError(issues)), [
            {"loc": ["hydrology", "rivers", 2, "from", "uid"], "msg": "Field required", "code": "missing",
             "schema_id": "SCH-HYDRO"},
            {"loc": ["widths", 0], "msg": "bad", "code": "UNKNOWN_ENUM"},
            {"loc": [], "msg": "broken bundle", "code": "BUNDLE_INVALID"},
            {"loc": ["widths", 1], "msg": "broken", "code": "broken"},
        ])
        report = ImportValidationReport(issues[2:3])
        self.assertEqual(report.to_dict(), {"validate_only": True, "valid": False,
                                            "issues": [{"loc": [], "msg": "broken bundle", "code": "BUNDLE_INVALID"}]})
        self.assertTrue(ImportValidationReport().valid)
        with self.assertRaises(ValidationError):
            ImportValidationReport(({"code": "x"},))  # pyright: ignore[reportArgumentType]


if __name__ == "__main__":
    unittest.main()
