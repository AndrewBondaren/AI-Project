import unittest
from uuid import UUID

from pydantic import ValidationError
from unittest.mock import patch
from app.application.publication.encoding.preparationSourceBindingCodec import PreparationSourceBindingCodec
from app.encoding.canonicalCodec import CanonicalEncodingError
from app.dataModel.fields.checkedPath import CheckedPath

from app.application.publication.validation.preparationSourceBindingValidator import PreparationSourceBindingValidator
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, PinHolder, VerifiedArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.publication.preparationSourceAuthority import (
    PreparationSourceBinding, PinnedManifestSourceOrigin, PreparationSourceOriginKind,
)
from app.dataModel.publication.preparationSourceBindingIssue import PreparationSourceBindingFieldCode as Code
from app.dataModel.publication.preparationSourceBindingIssue import PreparationSourceBindingShapeIssue as ShapeIssue
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
    def test_root_and_unknown_fields_keep_full_location_and_relations(self):
        validator = PreparationSourceBindingValidator()
        issues = validator.validate(None)
        self.assertEqual(len(issues), 1)
        self.assertIs(type(issues[0]), ShapeIssue)
        self.assertEqual(issues[0].location, ())
        value = binding()
        value = value.model_copy(update={"target": value.target.model_copy(update={"world_uid": "foreign"})})
        raw = dict(value)
        raw["extra"] = True
        raw["origin"] = dict(value.origin) | {"nested_extra": True}
        issues = validator.validate(raw)
        self.assertEqual(tuple(i.code for i in issues),
                         (Code.INVALID_SHAPE, Code.INVALID_SHAPE, Code.WORLD_MISMATCH, Code.WORLD_MISMATCH))
        self.assertEqual(tuple(i.location for i in issues[:2]), (("origin", "nested_extra"), ("extra",)))
        with patch("app.application.publication.encoding.preparationSourceBindingCodec.encode") as encode:
            with self.assertRaises(CanonicalEncodingError) as caught:
                PreparationSourceBindingCodec().encode(raw)
            self.assertEqual(caught.exception.args[0], issues)
            encode.assert_not_called()

    def test_shape_carrier_is_strict_frozen_and_required(self):
        value = ShapeIssue(code=Code.INVALID_SHAPE, location=(), message="root")
        for fields in ({"code": Code.WORLD_MISMATCH, "location": (), "message": "bad"},
                       {"code": Code.INVALID_SHAPE, "location": (True,), "message": "bad"},
                       {"code": Code.INVALID_SHAPE, "message": "missing"}):
            with self.assertRaises(ValidationError):
                ShapeIssue.model_validate(fields)
        with self.assertRaises(ValidationError):
            value.message = "changed"

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
        issues = PreparationSourceBindingValidator().validate(value.model_copy(update={"sources": (None,)}))
        self.assertEqual(tuple(i.code for i in issues), (Code.INVALID_SHAPE,))
        with self.assertRaises(ValidationError):
            PreparationSourceBinding.model_validate(value.model_dump() | {"extra": True})
        with self.assertRaises(ValidationError):
            value.sources = ()

    def test_malformed_sibling_keeps_worlds_and_later_source_indices(self):
        value = binding()
        child = value.origin.manifest.model_copy(update={"content_hash": "2" * 64})
        bad = VerifiedArtifactRef(ref=child, holder=PinHolder(pin_id="pin"))
        value = value.model_copy(update={"target": value.target.model_copy(update={"world_uid": "foreign"}),
                                        "sources": (None, bad, bad)})
        issues = PreparationSourceBindingValidator().validate(value)
        self.assertEqual(tuple(i.code for i in issues), (Code.INVALID_SHAPE, Code.WORLD_MISMATCH,
            Code.WORLD_MISMATCH, Code.INVALID_SOURCE_HOLDER, Code.DUPLICATE_SOURCE, Code.INVALID_SOURCE_HOLDER))
        locations = (("sources", 0), ("request", "world_uid"), ("origin", "pin", "world_uid"),
                     ("sources", 1, "holder"), ("sources", 2, "ref"), ("sources", 2, "holder"))
        self.assertEqual(tuple(i.path for i in issues), tuple(
            CheckedPath.from_pydantic_loc(PreparationSourceBinding, loc) for loc in locations))
        with patch("app.application.publication.encoding.preparationSourceBindingCodec.encode") as encode:
            with self.assertRaises(CanonicalEncodingError) as caught:
                PreparationSourceBindingCodec().encode(value)
            self.assertEqual(caught.exception.args[0], issues)
            encode.assert_not_called()

    def test_valid_fields_survive_malformed_other_fields(self):
        value = binding()
        request = value.request.model_copy(update={"proof": None})
        value = value.model_copy(update={"target": value.target.model_copy(update={"world_uid": "foreign"}),
                                        "request": request})
        issues = PreparationSourceBindingValidator().validate(value)
        self.assertEqual(tuple(i.code for i in issues),
                         (Code.INVALID_SHAPE, Code.WORLD_MISMATCH, Code.WORLD_MISMATCH))
