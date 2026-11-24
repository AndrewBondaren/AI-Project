"""Shared schema paths used by Snapshot admission and JSON diagnostics."""
import unittest
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError, create_model

from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.jsonValidation.resolution.wireIssues import field_issue, pydantic_issues
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.validatedFieldPath import FieldSegment, IndexSegment, ModelIdentity, VariantSegment
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


class MockCat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["cat"]
    age: int = Field(alias="years")


class MockDog(BaseModel):
    kind: Literal["dog"]
    age: int


class MockSection(BaseModel):
    payload: Annotated[MockCat | MockDog, Field(discriminator="kind")]


class MockRequest(BaseModel):
    sections: tuple[MockSection, ...]
    pets: tuple[Annotated[MockCat | MockDog, Field(discriminator="kind")], ...] = ()


class TaggedPathTests(unittest.TestCase):
    def test_nested_section_field_and_extra_keep_original_addresses(self) -> None:
        valid = {"payload": {"kind": "cat", "years": 3}}
        invalid = {"payload": {"kind": "cat", "years": "bad", "cat": 7}}
        with self.assertRaises(ValidationError) as caught:
            MockRequest.model_validate({"sections": (valid, valid, invalid)}, strict=True)
        before = caught.exception.errors()
        issues = pydantic_issues(ResolveContext(collect_only=True), MockRequest, caught.exception)
        self.assertEqual(caught.exception.errors(), before)
        self.assertEqual([item["loc"] for item in before], [
            ("sections", 2, "payload", "cat", "years"),
            ("sections", 2, "payload", "cat", "cat"),
        ])
        self.assertEqual(len(issues), 2)
        field, extra = issues
        self.assertIsInstance(field, JsonFieldError)
        assert isinstance(field, JsonFieldError)
        self.assertEqual(field.path.segments, (
            FieldSegment(owner=ModelIdentity.of(MockRequest), name="sections"),
            IndexSegment(index=2),
            FieldSegment(owner=ModelIdentity.of(MockSection), name="payload"),
            VariantSegment(branch=ModelIdentity.of(MockCat)),
            FieldSegment(owner=ModelIdentity.of(MockCat), name="age"),
        ))
        self.assertEqual(field.path.projection(), ("sections", 2, "payload", "age"))
        self.assertEqual(field.wire_path, ("sections", 2, "payload", "years"))
        self.assertEqual(field.location.parts, ())
        self.assertEqual(field.pydantic_type, "int_type")
        self.assertIsInstance(extra, WireShapeIssue)
        assert isinstance(extra, WireShapeIssue)
        self.assertEqual(extra.location.parts, ("sections", 2, "payload", "cat"))
        self.assertEqual(extra.pydantic_type, "extra_forbidden")

    def test_annotation_on_tuple_element_preserves_tag(self) -> None:
        loc = ("pets", 4, "cat", "years")
        path = CheckedPath.from_pydantic_loc(MockRequest, loc)
        self.assertIsNotNone(path)
        assert path is not None
        self.assertEqual(path.projection(), ("pets", 4, "age"))
        self.assertEqual(path.segments[2], VariantSegment(branch=ModelIdentity.of(MockCat)))

    def test_outer_plain_union_and_inner_discriminator_both_remain_typed(self) -> None:
        other = create_model("OtherSection", payload=(str, ...))
        root = create_model("MixedRequest", sections=(tuple[MockSection | other, ...], ...))
        loc = ("sections", 2, "MockSection", "payload", "cat", "years")
        issue = field_issue(ResolveContext(collect_only=True), root, loc,
                            "Input should be a valid integer", JsonValidationCode.SCHEMA_VIOLATION, "int_type")
        self.assertIsInstance(issue, JsonFieldError)
        assert isinstance(issue, JsonFieldError)
        self.assertEqual(issue.wire_path, ("sections", 2, "payload", "years"))
        self.assertEqual([s.branch for s in issue.path.segments if isinstance(s, VariantSegment)],
                         [ModelIdentity.of(MockSection), ModelIdentity.of(MockCat)])

    def test_root_model_shape_does_not_leak_synthetic_root_or_tag(self) -> None:
        class MockRows(RootModel[tuple[MockSection, ...]]):
            pass

        issue = field_issue(ResolveContext(collect_only=True), MockRows,
                            (2, "payload", "cat", "extra"), "Extra inputs are not permitted",
                            JsonValidationCode.SCHEMA_VIOLATION, "extra_forbidden")
        self.assertIsInstance(issue, WireShapeIssue)
        self.assertEqual(issue.location.parts, (2, "payload", "extra"))

    def test_unknown_tag_and_plain_duplicate_names_do_not_pick_a_branch(self) -> None:
        for tag in ("unknown", "MockCat"):
            self.assertIsNone(CheckedPath.from_pydantic_loc(MockRequest, ("pets", 0, tag, "years")))
        left = create_model("Same", value=(int, ...))
        right = create_model("Same", value=(str, ...))
        root = create_model("AmbiguousRoot", choice=(left | right, ...))
        self.assertIsNone(CheckedPath.from_pydantic_loc(root, ("choice", "Same", "value")))

    def test_ambiguous_declared_tags_are_unresolved(self) -> None:
        other_cat = create_model("OtherCat", kind=(Literal["cat"], ...), age=(int, ...))
        root = create_model("InvalidTaggedRoot", choice=(MockCat | other_cat, ...))
        # Simulate a corrupted schema without asking Pydantic to accept duplicate tags.
        root.model_fields["choice"].discriminator = "kind"
        self.assertIsNone(CheckedPath.from_pydantic_loc(root, ("choice", "cat", "age")))

    def test_shape_mapping_without_raw_input_uses_same_schema_resolver(self) -> None:
        issue = field_issue(ResolveContext(collect_only=True), MockRequest,
                            ("sections", 2, "payload", "cat", "extra"),
                            "Extra inputs are not permitted", JsonValidationCode.SCHEMA_VIOLATION,
                            "extra_forbidden")
        self.assertIsInstance(issue, WireShapeIssue)
        self.assertEqual(issue.location.parts, ("sections", 2, "payload", "extra"))
