"""Remaining G1.1 values and diagnostics; no runtime admission assertions."""

import unittest

from pydantic import ValidationError

from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.sourceVersioning.sourceBodyVersion import SourceBodyVersion, SourceCollectionVersion
from app.dataModel.sourceVersioning.sourceCapture import SourceCapture
from app.dataModel.sourceVersioning.sourceCaptureWitness import SourceCaptureWitness
from app.dataModel.sourceVersioning.sourceCollection import SourceCollectionBody
from app.dataModel.sourceVersioning.sourceDescriptor import SourceDescriptorCategory as Category
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceErrors import (
    SourceFailure, SourceFieldCode, SourceFieldIssue, SourceLogicCode, SourceLogicIssue, SourceOperation,
)
from app.dataModel.sourceVersioning.sourceObjectId import RegistryMemberId, SourceCollectionId
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.dataModel.sourceVersioning.sourceProofGroups import (
    SourceProofGroupsInput, SourceProofGroupsResult, SourceProofGroupsVerifyInput,
)
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput, SourceProofReadInput
from app.dataModel.sourceVersioning.sourceProofResult import SourceProofResult
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection, SourceProofSelectInput
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.validation.immutableValue import validate_immutable


def artifact(key="source.capture"):
    return ArtifactRef(kind=ArtifactKind.BLOB, format_key=RegistryKey(key), format_version=1,
                       content_hash="0" * 64, nbytes=123, row_count=None)


def collection(world="w"):
    return SourceCollectionId(kind=Category.COLLECTION, world_uid=world, descriptor=RegistryKey("membership"))


def member(world="w"):
    return RegistryMemberId(kind=Category.REGISTRY_MEMBER, world_uid=world,
                            descriptor=RegistryKey("member"), member_key="plains")


def revision():
    return SourceRevision(seq=1, content_hash="1" * 64)


def empty_proof():
    return SourceDurableProof(schema_version=1, world_uid="w", uses=())


class FoundationTests(unittest.TestCase):
    def test_capture_graph(self):
        obj = SourceBodyVersion(source=SourceVersionRef(object_id=member(), revision=revision()), body=artifact("terrain"))
        group = SourceCollectionVersion(source=SourceCollectionVersionRef(collection_id=collection(), revision=revision()),
                                        body=artifact("membership"))
        values = (obj, group, SourceCollectionBody(collection=collection(), members=(member(),)),
                  SourceCapture(world_uid="w", objects=(obj,), collections=(group,)),
                  SourceCaptureWitness(capture_uid="capture", world_uid="w", capture_body=artifact()))
        for value in values:
            with self.subTest(owner=type(value).__name__):
                self.assertEqual(type(value).model_validate_json(value.model_dump_json()), value)
                validate_immutable(value)
        for objects, collections in (((obj, obj), ()), ((), (group, group))):
            with self.assertRaises(ValidationError):
                SourceCapture(world_uid="w", objects=objects, collections=collections)
        with self.assertRaises(ValidationError):
            SourceCapture(world_uid="foreign", objects=(obj,), collections=(group,))

    def test_collection_and_witness_shape(self):
        for members in ((member(), member()), (member("foreign"),)):
            with self.assertRaises(ValidationError):
                SourceCollectionBody(collection=collection(), members=members)
        with self.assertRaises(ValidationError):
            SourceCaptureWitness(capture_uid="capture", world_uid="w", capture_body=artifact("source.capture-witness"))
        with self.assertRaises(ValidationError):
            SourceBodyVersion.model_validate(dict(source=SourceCollectionVersionRef(
                collection_id=collection(), revision=revision()), body=artifact()))

    def test_exact_read_and_select_requests(self):
        proof = empty_proof()
        selection = SourceProofSelection(proof_fingerprint="1" * 64, dependency_indices=())
        for value in (SourceProofReadInput(world_uid="w", proof=proof),
                      SourceProofSelectInput(world_uid="w", proof=proof, selection=selection)):
            self.assertEqual(type(value).model_validate_json(value.model_dump_json()), value)
            self.assertEqual(value.proof, proof)
            with self.assertRaises(ValidationError):
                type(value).model_validate(value.model_dump() | {"world_uid": "foreign"})
        for fields in ({"proof": proof}, {"world_uid": "w", "uses": ()}):
            with self.assertRaises(ValidationError):
                SourceProofReadInput.model_validate(fields)

    def test_verify_request_correlation(self):
        expected = SourceProofGroupsInput(groups=(SourceProofInput(world_uid="w", uses=()),))
        selection = SourceProofSelection(proof_fingerprint="1" * 64, dependency_indices=())
        result = SourceProofGroupsResult(admission=SourceProofResult(proof=empty_proof(), durable_refs=()),
                                         selections=(selection,))
        request = SourceProofGroupsVerifyInput(expected=expected, result=result)
        self.assertEqual(SourceProofGroupsVerifyInput.model_validate_json(request.model_dump_json()), request)
        with self.assertRaises(ValidationError):
            SourceProofGroupsVerifyInput(expected=expected, result=SourceProofGroupsResult(
                admission=result.admission, selections=(selection, selection)))

    def test_typed_errors_and_shared_aggregation(self):
        world = CheckedPath.root(SourceProofReadInput).field(FieldRef(
            lambda: SourceProofReadInput, lambda request: request.world_uid)).freeze()
        proof = CheckedPath.root(SourceProofReadInput).field(FieldRef(
            lambda: SourceProofReadInput, lambda request: request.proof)).freeze()
        issues = (SourceFieldIssue(code=SourceFieldCode.INVALID_SHAPE, path=world, message="world"),
                  SourceFieldIssue(code=SourceFieldCode.NON_CANONICAL_PROOF, path=proof, message="proof"))
        collector = ValidatorAggregationHelper((SourceFieldIssue,))
        for issue in issues:
            collector.add(issue)
        failure = SourceFailure(operation=SourceOperation.READ, field_issues=collector.snapshot(), logic_issues=())
        self.assertEqual(failure.field_issues, issues)
        self.assertEqual(tuple(i.path for i in failure.field_issues), (world, proof))
        validate_immutable(failure)
        self.assertEqual(tuple(SourceFieldIssue.model_fields), ("code", "path", "message"))
        with self.assertRaises(ValidationError):
            issues[0].code = SourceFieldCode.INVALID_IDENTITY
        with self.assertRaises(ValidationError):
            failure.operation = SourceOperation.ADMIT
        with self.assertRaises(ValidationError):
            SourceFailure(operation=SourceOperation.READ, field_issues=(), logic_issues=())

    def test_logic_error_context_required_and_strict(self):
        fields = dict(code=SourceLogicCode.WRONG_WORLD, group_index=None, use_index=None, source=None, artifact=None)
        issue = SourceLogicIssue.model_validate(fields)
        self.assertIsNone(issue.group_index)
        for key in ("group_index", "use_index", "source", "artifact"):
            with self.subTest(missing=key), self.assertRaises(ValidationError):
                SourceLogicIssue.model_validate({k: v for k, v in fields.items() if k != key})
        for index in (True, -1, "0", 0.0):
            with self.subTest(index=index), self.assertRaises(ValidationError):
                SourceLogicIssue.model_validate(fields | {"use_index": index})
        failure = SourceFailure(operation=SourceOperation.CHECK_COVERAGE, field_issues=(), logic_issues=(issue,))
        self.assertEqual(SourceFailure.model_validate_json(failure.model_dump_json()), failure)

    def test_nested_error_and_capture_revalidation(self):
        forged = SourceLogicIssue.model_construct(code=SourceLogicCode.WRONG_WORLD, group_index=True,
                                                  use_index=None, source=None, artifact=None)
        with self.assertRaises(ValidationError):
            SourceFailure(operation=SourceOperation.READ, field_issues=(), logic_issues=(forged,))
        forged_ref = SourceVersionRef.model_construct(object_id=member(), revision=SourceRevision.model_construct(
            seq=True, content_hash="1" * 64))
        with self.assertRaises(ValidationError):
            SourceCapture(world_uid="w", objects=(SourceBodyVersion.model_construct(source=forged_ref, body=artifact()),),
                          collections=())


if __name__ == "__main__":
    unittest.main()
