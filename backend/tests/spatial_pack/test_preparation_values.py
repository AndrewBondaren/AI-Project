import unittest

from pydantic import ValidationError

from app.application.worldData.pack.preparation.errors import PackPreparationFailure
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.worldPack.meta.parts import PackStoredPart
from app.dataModel.worldPack.preparation.addresses import PackCoarseClimateAddress, PackMapTileAddress
from app.dataModel.worldPack.preparation.errors import PackPreparationError, PackPreparationFailureReason
from app.dataModel.worldPack.preparation.parts import PackMapTilePartInput
from app.dataModel.worldPack.preparation.provenance import PackNewPartProvenance, PackStoredProvenance


class PreparationValuesTests(unittest.TestCase):
    def setUp(self):
        self.proof = SourceDurableProof(schema_version=1, world_uid="world", uses=())
        self.provenance = PackStoredProvenance(source_proof=self.proof, planning=())
        self.ref = ArtifactRef(kind=ArtifactKind.BLOB, format_key="test.payload", format_version=1,
                               content_hash="a" * 64, nbytes=1)
        self.address = PackMapTileAddress(kind="map_tile", gx=0, gy=0)

    def test_named_input_and_stored_provenance_are_distinct(self):
        part = PackMapTilePartInput(address=self.address, artifact=self.ref,
            provenance=PackNewPartProvenance(kind="new", provenance=self.provenance))
        stored = PackStoredPart(address=part.address, artifact=part.artifact,
                                provenance=part.provenance.provenance)
        self.assertEqual(stored.provenance.source_proof, self.proof)
        self.assertNotIn("kind", type(stored.provenance).model_fields)
        with self.assertRaises(ValidationError):
            PackMapTilePartInput(address=PackCoarseClimateAddress(kind="climate_coarse"),
                                artifact=self.ref, provenance=part.provenance)

    def test_nested_forged_source_and_ref_are_revalidated(self):
        for provenance, ref in (
            (self.provenance.model_copy(update={"source_proof": self.proof.model_copy(update={"schema_version": True})}), self.ref),
            (self.provenance, self.ref.model_copy(update={"nbytes": True})),
        ):
            with self.subTest(provenance=provenance, ref=ref), self.assertRaises(ValidationError):
                PackStoredPart(address=self.address, artifact=ref, provenance=provenance)

    def test_required_strict_immutable_fields(self):
        with self.assertRaises(ValidationError):
            PackStoredProvenance(source_proof=self.proof)
        with self.assertRaises(ValidationError):
            PackStoredProvenance(source_proof=self.proof, planning=[])
        with self.assertRaises(ValidationError):
            self.provenance.source_proof = self.proof

    def test_only_oversize_can_omit_field_diagnostics(self):
        for reason in PackPreparationFailureReason:
            with self.subTest(reason=reason):
                if reason is PackPreparationFailureReason.MANIFEST_OVERSIZE:
                    error = PackPreparationError(reason=reason, issues=())
                    self.assertEqual(PackPreparationFailure(error).error, error)
                else:
                    with self.assertRaises(ValidationError):
                        PackPreparationError(reason=reason, issues=())

    def test_structural_issues_keep_order_and_require_invalid_input(self):
        issues = tuple(WireShapeIssue(code=JsonValidationCode.EXPECTED_OBJECT,
                      location=WireLocation(parts=(name,)), message="expected object") for name in ("first", "second"))
        error = PackPreparationError(reason=PackPreparationFailureReason.INVALID_INPUT, issues=issues)
        self.assertEqual(error.issues, issues)
        with self.assertRaises(ValidationError):
            PackPreparationError(reason=PackPreparationFailureReason.DEPENDENCY_MISMATCH, issues=issues)
        forged = error.model_copy(update={"issues": ()})
        with self.assertRaises(ValidationError):
            PackPreparationFailure(forged)
