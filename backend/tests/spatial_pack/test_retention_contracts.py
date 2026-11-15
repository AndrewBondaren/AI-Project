import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from app.application.worldData.pack.preparation.errors import (
    PackPreparationFailure, preparation_errors, raise_preparation_errors,
)
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.worldPack.preparation.errors import (
    PackPreparationArtifactIssue, PackPreparationError, PackPreparationFailureReason,
    PackPreparationIssue, PackPreparationIssueCode, PackPreparationRetentionLimitIssue, PackRetentionResource,
)
from app.dataModel.worldPack.preparation.retentionGraph import PackRetentionBudget, PackRetentionCollectInput


class RetentionContractTests(unittest.TestCase):
    def setUp(self):
        self.ref = ArtifactRef(kind=ArtifactKind.BLOB, format_key="test.payload", format_version=1,
                               content_hash="a" * 64, nbytes=4)
        self.shape = WireShapeIssue(code=JsonValidationCode.EXPECTED_OBJECT,
                                    location=WireLocation(parts=("unknown",)), message="expected object")
        self.wrapped = PackPreparationArtifactIssue(artifact=self.ref, issue=self.shape)
        self.limit = PackPreparationRetentionLimitIssue(
            code=PackPreparationIssueCode.RETENTION_LIMIT_EXCEEDED,
            resource=PackRetentionResource.READ_BYTES, limit=10, consumed=8, requested=4,
            artifact=self.ref)

    def test_interruption_preserves_prior_diagnostics_and_stops_next_stage(self):
        errors = preparation_errors()
        second = self.wrapped.model_copy(update={"artifact": self.ref.model_copy(update={"content_hash": "b" * 64})})
        for issue in (self.shape, self.wrapped, second, self.limit):
            errors.add(issue)
        dependent = Mock()
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
            dependent()
        dependent.assert_not_called()
        self.assertIs(caught.exception.error.reason, PackPreparationFailureReason.RESOURCE_LIMIT)
        self.assertEqual(caught.exception.error.issues, (self.shape, self.wrapped, second, self.limit))
        self.assertEqual(self.wrapped.issue.location.parts, ("unknown",))

    def test_wrapper_preserves_structural_reason_without_limit(self):
        errors = preparation_errors()
        errors.add(self.wrapped)
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(errors, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        self.assertIs(caught.exception.error.reason, PackPreparationFailureReason.INVALID_INPUT)
        for issue in (self.wrapped, self.limit):
            with self.assertRaises(ValidationError):
                PackPreparationArtifactIssue(artifact=self.ref, issue=issue)

    def test_typed_payload_path_and_code_survive_wrapper_and_limit(self):
        path = CheckedPath.root(PackRetentionCollectInput).field(FieldRef(
            lambda: PackRetentionCollectInput, lambda value: value.world_uid)).freeze()
        inner = PackPreparationIssue(code=PackPreparationIssueCode.IDENTITY_MISMATCH,
                                     path=path, message="foreign world")
        wrapped = PackPreparationArtifactIssue(artifact=self.ref, issue=inner)
        errors = preparation_errors()
        errors.add(wrapped)
        errors.add(self.limit)
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(errors, PackPreparationFailureReason.IDENTITY_CONFLICT)
        self.assertEqual(caught.exception.error.issues, (wrapped, self.limit))
        self.assertEqual(wrapped.issue.path, path)
        self.assertIs(wrapped.issue.code, PackPreparationIssueCode.IDENTITY_MISMATCH)

    def test_limit_is_required_once_at_end_only_for_resource_reason(self):
        for reason, issues in (
            (PackPreparationFailureReason.RESOURCE_LIMIT, (self.wrapped,)),
            (PackPreparationFailureReason.RESOURCE_LIMIT, (self.limit, self.wrapped)),
            (PackPreparationFailureReason.RESOURCE_LIMIT, (self.limit, self.limit)),
            (PackPreparationFailureReason.INVALID_INPUT, (self.limit,)),
        ):
            with self.subTest(reason=reason, issues=issues), self.assertRaises(ValidationError):
                PackPreparationError(reason=reason, issues=issues)

    def test_invalid_reservations_and_forged_nested_values_are_rejected(self):
        for update in ({"consumed": 6}, {"consumed": 11}, {"requested": 5},
                       {"consumed": True}, {"requested": 0}, {"limit": 0},
                       {"artifact": self.ref.model_copy(update={"nbytes": True})}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                PackPreparationRetentionLimitIssue.model_validate(self.limit.model_copy(update=update))
        value = self.limit.model_copy(update={"resource": PackRetentionResource.ARTIFACTS,
                                             "limit": 2, "consumed": 2, "requested": 1})
        self.assertEqual(PackPreparationRetentionLimitIssue.model_validate(value), value)

    def test_input_and_policy_are_required_strict_and_frozen(self):
        request = PackRetentionCollectInput(manifest=self.ref, world_uid="world")
        budget = PackRetentionBudget(max_read_bytes=10, max_artifacts=2)
        for raw in ({}, {"max_read_bytes": True, "max_artifacts": 2},
                    {"max_read_bytes": 0, "max_artifacts": 2},
                    {"max_read_bytes": 10, "max_artifacts": 2, "extra": 1}):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                PackRetentionBudget.model_validate(raw)
        with self.assertRaises(ValidationError):
            budget.max_artifacts = 3
        with self.assertRaises(ValidationError):
            PackRetentionCollectInput.model_validate(request.model_copy(
                update={"manifest": self.ref.model_copy(update={"nbytes": True})}))
