import unittest
from typing import Annotated

from pydantic import AfterValidator, BaseModel

from app.application.jsonValidation.bundle.connectionGraph import normalize_bundle_connections
from app.application.jsonValidation.bundle.preflight import validate_rows
from app.application.jsonValidation.index.validate import _index_issue
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.jsonValidation.types import ImportValidationError, import_validation_http_detail, wire_loc
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.validation.importIssues.wireLocation import WireLocation


class BundleIssueTests(unittest.TestCase):
    def test_multi_column_index_requires_a_registered_world_key(self):
        def issue(key):
            return _index_issue(WireLocation(parts=("world",)), model=WorldClimateScalars,
                                path=(key,), message="missing target", code=JsonValidationCode.REF_W_UNKNOWN)

        with self.assertRaises(RuntimeError):
            issue("wrong_column")
        valid = issue("precipitation_liquid")
        self.assertIsInstance(valid, JsonFieldError)
        self.assertEqual(wire_loc(valid), ("world", "precipitation_liquid"))
        self.assertEqual(valid.schema_id, WorldClimateScalars.SCHEMA_ID)

    def test_preflight_preserves_dictionary_keys_resembling_branch_labels(self):
        class Row(BaseModel):
            values: dict[str, int]

        keys = ("function-main", "is-instance[custom]", "function-after[f(), int]")
        ctx = ResolveContext.for_import(validate_only=True).child("rows")
        with self.assertRaises(UnresolvedModelError) as caught:
            validate_rows([{"values": dict.fromkeys(keys, "bad")}], Row.model_validate, ctx=ctx)
        self.assertEqual([wire_loc(i) for i in caught.exception.issues], [("rows", 0, "values", k) for k in keys])
        self.assertEqual([i.pydantic_type for i in caught.exception.issues], ["int_parsing"] * len(keys))

    def test_union_wrapper_labels_do_not_become_wire_keys(self):
        def unchanged(value):
            return value

        class Row(BaseModel):
            value: Annotated[int, AfterValidator(unchanged)] | Annotated[float, AfterValidator(unchanged)]

        ctx = ResolveContext.for_import(validate_only=True).child("rows")
        with self.assertRaises(UnresolvedModelError) as caught:
            validate_rows([{"value": "bad"}], Row.model_validate, ctx=ctx)
        self.assertEqual([(wire_loc(i), i.pydantic_type) for i in caught.exception.issues], [
            (("rows", 0, "value"), "int_parsing"), (("rows", 0, "value"), "float_parsing"),
        ])

    def test_collects_section_row_and_reference_issues_under_parent(self):
        ctx = ResolveContext.for_import(validate_only=True).child("bundle")
        edge = dict(edge_uid="edge", from_node_uid="a", to_node_uid="b", graph_level="world",
                    connection_type="absent")
        with self.assertRaises(ImportValidationError) as caught:
            normalize_bundle_connections({"connection_nodes": {}, "connection_edges": [None, edge]}, ctx=ctx)
        section, row, reference = caught.exception.errors
        self.assertIsInstance(section, WireShapeIssue)
        self.assertEqual(section.code, JsonValidationCode.EXPECTED_LIST)
        self.assertEqual(wire_loc(section), ("bundle", "connection_nodes"))
        self.assertEqual(row.code, JsonValidationCode.EXPECTED_OBJECT)
        self.assertEqual(wire_loc(row), ("bundle", "connection_edges", 0))
        self.assertIsInstance(reference, JsonFieldError)
        self.assertEqual(reference.code, JsonValidationCode.REF_W_UNKNOWN)
        self.assertEqual(wire_loc(reference), ("bundle", "connection_edges", 1, "connection_type"))

    def test_preflight_preserves_pydantic_wire_code(self):
        class Row(BaseModel):
            count: int

        ctx = ResolveContext.for_import(validate_only=True).child("rows")
        with self.assertRaises(UnresolvedModelError) as caught:
            validate_rows([{"count": []}], Row.model_validate, ctx=ctx)
        issue, = caught.exception.issues
        self.assertIsInstance(issue, WireShapeIssue)
        self.assertEqual(issue.code, JsonValidationCode.SCHEMA_VIOLATION)
        detail, = import_validation_http_detail(ImportValidationError([issue]))
        self.assertEqual(detail["code"], "int_type")
        self.assertEqual(detail["loc"], ["rows", 0, "count"])
