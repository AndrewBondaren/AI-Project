import unittest
from uuid import UUID

from pydantic import ValidationError

from app.application.publication.validation.preparationSourceBindingValidator import PreparationSourceBindingValidator
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, PinHolder, VerifiedArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.publication.preparationSourceAuthority import (
    PreparationSourceBinding, PinnedManifestSourceOrigin, PreparationSourceOriginKind,
)
from app.dataModel.publication.preparationSourceBindingIssue import PreparationSourceBindingFieldCode as Code
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.worldPack.read.pinnedManifest import ManifestPinRead
from tests.sourceVersioning.test_canonical import vector1


def binding():
    proof = vector1()
    manifest = proof.uses[0].capture.artifact
    return PreparationSourceBinding(
        target=OperationLeaseRef(operation_id="op", world_uid="world-test", kind=OperationKind.PACK_ACTIVATION,
                                 preparation_fingerprint="1" * 64, fence=1),
        request=SourceProofReadInput(world_uid="world-test", proof=proof),
        origin=PinnedManifestSourceOrigin(kind=PreparationSourceOriginKind.PINNED_MANIFEST,
            pin=ManifestPinRead(store_id=UUID(int=1), execution_id="exec", invocation_id="inv",
                                logical_read_key="base", pin_id="pin", world_uid="world-test", max_bytes=1024),
            manifest=manifest), sources=())


class PreparationSourceBindingTests(unittest.TestCase):
    def test_empty_and_root_child(self):
        value = binding()
        validator = PreparationSourceBindingValidator()
        self.assertEqual(validator.validate(value), ())
        child = value.origin.manifest.model_copy(update={"content_hash": "2" * 64})
        sources = (VerifiedArtifactRef(ref=value.origin.manifest, holder=PinHolder(pin_id="pin")),
                   VerifiedArtifactRef(ref=child, holder=ArtifactRetentionHolder(artifact=value.origin.manifest)))
        self.assertEqual(validator.validate(value.model_copy(update={"sources": sources})), ())

    def test_independent_relations_keep_indices_and_order(self):
        value = binding()
        child = value.origin.manifest.model_copy(update={"content_hash": "2" * 64})
        bad = VerifiedArtifactRef(ref=child, holder=PinHolder(pin_id="pin"))
        value = value.model_copy(update={
            "target": value.target.model_copy(update={"world_uid": "foreign"}), "sources": (bad, bad)})
        issues = PreparationSourceBindingValidator().validate(value)
        self.assertEqual(tuple(i.code for i in issues), (
            Code.WORLD_MISMATCH, Code.WORLD_MISMATCH, Code.INVALID_SOURCE_HOLDER,
            Code.DUPLICATE_SOURCE, Code.INVALID_SOURCE_HOLDER))
        self.assertNotEqual(issues[2].path, issues[4].path)
        self.assertEqual(issues, PreparationSourceBindingValidator().validate(value))

    def test_structural_revalidation(self):
        value = binding()
        with self.assertRaises(ValidationError):
            PreparationSourceBindingValidator().validate(value.model_copy(update={"sources": (None,)}))
        with self.assertRaises(ValidationError):
            PreparationSourceBinding.model_validate(value.model_dump() | {"extra": True})
        with self.assertRaises(ValidationError):
            value.sources = ()
