import unittest

from pydantic import BaseModel

from app.application.jsonValidation.bundle.connectionGraph import normalize_bundle_connections
from app.application.jsonValidation.bundle.preflight import validate_rows
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.jsonValidation.types import ImportValidationError, import_validation_http_detail, wire_loc
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class BundleIssueTests(unittest.TestCase):
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
