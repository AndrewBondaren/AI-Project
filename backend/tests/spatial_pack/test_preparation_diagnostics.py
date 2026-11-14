import unittest
from unittest.mock import Mock, patch

from app.application.worldData.pack.preparation.errors import (
    PackPreparationFailure,
    preparation_errors,
    raise_preparation_errors,
    validate_preparation_input,
)
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.validation.diagnostics.validatorAggregationHelper import IssueAdmissionError
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.worldPack.preparation.addresses import PackMapTileAddress
from app.dataModel.worldPack.preparation.errors import (
    PackPreparationFailureReason,
    PackPreparationIssue,
    PackPreparationIssueCode,
)
from app.dataModel.worldPack.preparation.parts import PackMapTilePartInput
from app.dataModel.worldPack.preparation.provenance import PackNewPartProvenance, PackStoredProvenance


class PreparationDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.address = PackMapTileAddress(kind="map_tile", gx=0, gy=0)
        self.part = PackMapTilePartInput(
            address=self.address,
            artifact=ArtifactRef(kind=ArtifactKind.BLOB, format_key="test.payload", format_version=1,
                                 content_hash="a" * 64, nbytes=1),
            provenance=PackNewPartProvenance(kind="new", provenance=PackStoredProvenance(
                source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=()),
                planning=(),
            )),
        )

    def test_nested_errors_are_aggregated_before_dependent_work(self):
        forged = self.part.model_copy(update={
            "address": self.address.model_copy(update={"gx": True, "gy": "bad"}),
            "artifact": self.part.artifact.model_copy(update={"nbytes": False}),
        })
        stage = preparation_errors()
        dependent_work = Mock()
        with self.assertRaises(PackPreparationFailure) as caught:
            value = validate_preparation_input(PackMapTilePartInput, forged, stage)
            raise_preparation_errors(stage, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
            dependent_work(value)
        dependent_work.assert_not_called()
        error = caught.exception.error
        self.assertIs(error.reason, PackPreparationFailureReason.INVALID_INPUT)
        self.assertEqual([type(issue) for issue in error.issues], [JsonFieldError] * 3)
        self.assertEqual([issue.path.projection() for issue in error.issues],
                         [("address", "gx"), ("address", "gy"), ("artifact", "nbytes")])
        self.assertTrue(all(issue.code is JsonValidationCode.SCHEMA_VIOLATION for issue in error.issues))
        self.assertTrue(all(issue.pydantic_type == "int_type" for issue in error.issues))
        self.assertIs(forged.address.gx, True)
        self.assertEqual(self.part.address.gx, 0)

    def test_unknown_key_has_wire_location_without_invented_field_path(self):
        forged = self.address.model_copy(update={"unexpected": 1})
        stage = preparation_errors()
        self.assertIsNone(validate_preparation_input(PackMapTileAddress, forged, stage))
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(stage, PackPreparationFailureReason.INVALID_INPUT)
        issue, = caught.exception.error.issues
        self.assertIs(type(issue), WireShapeIssue)
        self.assertEqual(issue.location.parts, ("unexpected",))
        self.assertEqual(issue.pydantic_type, "extra_forbidden")

    def test_mixed_stage_keeps_semantic_issue_and_structural_reason(self):
        path = CheckedPath.root(PackMapTileAddress).field(
            FieldRef(lambda: PackMapTileAddress, lambda value: value.gx)
        ).freeze()
        semantic = PackPreparationIssue(code=PackPreparationIssueCode.ADDRESS_MISMATCH,
                                        path=path, message="address does not match")
        stage = preparation_errors()
        stage.add(semantic)
        validate_preparation_input(PackMapTileAddress, self.address.model_copy(update={"gy": True}), stage)
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(stage, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        self.assertIs(caught.exception.error.reason, PackPreparationFailureReason.INVALID_INPUT)
        self.assertEqual(caught.exception.error.issues[0], semantic)
        self.assertIs(type(caught.exception.error.issues[1]), JsonFieldError)

    def test_valid_input_does_not_produce_failure_or_coerce_values(self):
        stage = preparation_errors()
        self.assertEqual(validate_preparation_input(PackMapTilePartInput, self.part, stage), self.part)
        raise_preparation_errors(stage, PackPreparationFailureReason.INVALID_INPUT)

    def test_semantic_only_stage_preserves_reason(self):
        stage = preparation_errors()
        path = CheckedPath.root(PackMapTileAddress).field(
            FieldRef(lambda: PackMapTileAddress, lambda value: value.gx)
        ).freeze()
        stage.add(PackPreparationIssue(code=PackPreparationIssueCode.ADDRESS_MISMATCH,
                                      path=path, message="address does not match"))
        with self.assertRaises(PackPreparationFailure) as caught:
            raise_preparation_errors(stage, PackPreparationFailureReason.DEPENDENCY_MISMATCH)
        self.assertIs(caught.exception.error.reason, PackPreparationFailureReason.DEPENDENCY_MISMATCH)

    def test_adapter_defects_and_infrastructure_errors_are_not_input_refusals(self):
        module = "app.application.worldData.pack.preparation.errors"
        with patch(module + ".pydantic_issues", return_value=[object()]):
            with self.assertRaises(IssueAdmissionError):
                validate_preparation_input(
                    PackMapTileAddress, self.address.model_copy(update={"gx": True}), preparation_errors()
                )
        for error in (OSError("storage failed"), RuntimeError("validator defect")):
            with self.subTest(error=error), patch.object(PackMapTileAddress, "model_validate", side_effect=error):
                with self.assertRaises(type(error)) as caught:
                    validate_preparation_input(PackMapTileAddress, self.address, preparation_errors())
                self.assertIs(caught.exception, error)
