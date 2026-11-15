"""Atom and selection invariants; no finalized-provenance claim."""

import unittest

from pydantic import ValidationError

from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1
from app.application.worldData.sourceVersioning.proof.atomIndex import SourceProofAtomIndex
from app.application.worldData.sourceVersioning.proof.validation.sourceProofCanonicalChecker import SourceProofCanonicalChecker
from app.application.worldData.sourceVersioning.proof.validation.sourceSelectionChecker import SourceSelectionChecker
from app.application.worldData.sourceVersioning.proof.validation.sourceUsageConflictChecker import SourceUsageConflictChecker
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.registryKey import RegistryKey
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDescriptor import SourceDescriptorCategory
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceErrors import SourceFieldCode, SourceLogicCode
from app.dataModel.sourceVersioning.sourceObjectId import SourceCollectionId
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection, SourceProofSelectInput
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef
from app.encoding.canonicalCodec import CanonicalCodec, content_digest
from tests.sourceVersioning.test_canonical import vector1
from tests.sourceVersioning.test_core_invariants import proof_path


def mixed_proof():
    base = vector1()
    use = base.uses[0]
    collection = SourceCollectionVersionRef(collection_id=SourceCollectionId(
        kind=SourceDescriptorCategory.COLLECTION, world_uid=base.world_uid,
        descriptor=RegistryKey("members")), revision=use.dependencies.objects[0].revision)
    first = SourceCaptureUsage(capture=use.capture, dependencies=SourceDependencySet(
        objects=use.dependencies.objects, collections=(collection,)))
    second = SourceCaptureUsage(capture=use.capture.model_copy(update={
        "artifact": use.capture.artifact.model_copy(update={"content_hash": "f" * 64})}),
        dependencies=use.dependencies)
    return SourceDurableProof(schema_version=1, world_uid=base.world_uid, uses=(first, second))


def selection_path():
    return CheckedPath.root(SourceProofSelectInput).field(FieldRef(
        lambda: SourceProofSelectInput, lambda request: request.selection))


def fingerprint(proof):
    return content_digest(CanonicalCodec(SOURCE_PROOF_SCHEMA_V1).encode(proof)).hex()


class AtomTests(unittest.TestCase):
    def test_literal_order_capture_identity_and_immutability(self):
        proof = mixed_proof()
        self.assertEqual(SourceProofCanonicalChecker().check(proof, path=proof_path()), ())
        atoms = SourceProofAtomIndex().enumerate(proof)
        first, second = proof.uses
        self.assertEqual(atoms, (
            SourceCaptureUsage(capture=first.capture, dependencies=SourceDependencySet(
                objects=first.dependencies.objects, collections=())),
            SourceCaptureUsage(capture=first.capture, dependencies=SourceDependencySet(
                objects=(), collections=first.dependencies.collections)), second))
        self.assertNotEqual(atoms[0], atoms[2])
        self.assertEqual(proof.uses, (first, second))
        with self.assertRaises(TypeError):
            atoms[0] = atoms[2]

    def test_empty(self):
        proof = SourceDurableProof(schema_version=1, world_uid="w", uses=())
        self.assertEqual(SourceProofCanonicalChecker().check(proof, path=proof_path()), ())
        self.assertEqual(SourceProofAtomIndex().enumerate(proof), ())

    def test_collection_revision_conflict(self):
        proof = mixed_proof()
        capture = proof.uses[0].capture
        first = proof.uses[0].dependencies.collections[0]
        second = first.model_copy(update={"revision": SourceRevision(seq=2, content_hash="2" * 64)})
        issues = SourceUsageConflictChecker().check(captures=((None, 0, capture),),
            dependencies=((None, 0, 0, capture, first), (None, 0, 2, capture, second)))
        self.assertEqual(tuple(i.code for i in issues), (SourceLogicCode.REVISION_CONFLICT,))
        self.assertEqual(issues[0].source, second)

    def test_unsorted_uses_and_dependencies(self):
        proof = mixed_proof()
        reversed_proof = proof.model_copy(update={"uses": tuple(reversed(proof.uses))})
        self.assertEqual(len(SourceProofCanonicalChecker().check(reversed_proof, path=proof_path())), 1)
        first = proof.uses[0]
        obj = first.dependencies.objects[0]
        other_obj = obj.model_copy(update={"object_id": obj.object_id.model_copy(update={"member_key": "desert"})})
        col = first.dependencies.collections[0]
        other_col = col.model_copy(update={"collection_id": col.collection_id.model_copy(
            update={"descriptor": RegistryKey("others")})})
        codec = CanonicalCodec(SOURCE_PROOF_SCHEMA_V1)
        deps = SourceDependencySet(objects=tuple(sorted((obj, other_obj), key=codec.encode, reverse=True)),
            collections=tuple(sorted((col, other_col), key=codec.encode, reverse=True)))
        malformed = proof.model_copy(update={"uses": (first.model_copy(update={"dependencies": deps}),)})
        issues = SourceProofCanonicalChecker().check(malformed, path=proof_path())
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(i.code == SourceFieldCode.NON_CANONICAL_PROOF for i in issues))

    def test_pojo_and_checker_reject_same_persisted_value_violations(self):
        proof = mixed_proof()
        use = proof.uses[0]
        obj = use.dependencies.objects[0]
        collection = use.dependencies.collections[0]
        revision = SourceRevision(seq=2, content_hash="2" * 64)
        cases = (
            (use, use),
            (use.model_copy(update={"dependencies": SourceDependencySet(objects=(), collections=())}),),
            (use.model_copy(update={"dependencies": SourceDependencySet(
                objects=(obj, obj.model_copy(update={"revision": revision})), collections=())}),),
            (use.model_copy(update={"dependencies": SourceDependencySet(objects=(),
                collections=(collection, collection.model_copy(update={"revision": revision})))}),),
        )
        for uses in cases:
            with self.subTest(uses=uses):
                forged = proof.model_copy(update={"uses": uses})
                with self.assertRaises(ValidationError):
                    SourceDurableProof.model_validate(forged, strict=True)
                issues = SourceProofCanonicalChecker().check(forged, path=proof_path())
                self.assertEqual(tuple(i.code for i in issues), (SourceFieldCode.NON_CANONICAL_PROOF,))


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.checker = SourceSelectionChecker(SourceProofAtomIndex())
        self.proof = mixed_proof()
        self.assertEqual(SourceProofCanonicalChecker().check(self.proof, path=proof_path()), ())

    def check(self, selection):
        return self.checker.check(selection, proof=self.proof, path=selection_path(), selection_index=3)

    def test_valid_empty_and_repeat_calls(self):
        for indices in ((), (0, 2)):
            self.assertEqual(self.check(SourceProofSelection(proof_fingerprint=fingerprint(self.proof),
                dependency_indices=indices)), ())
        empty = SourceDurableProof(schema_version=1, world_uid="w", uses=())
        self.assertEqual(self.checker.check(SourceProofSelection(proof_fingerprint=fingerprint(empty),
            dependency_indices=()), proof=empty, path=selection_path(), selection_index=None), ())

    def test_wrong_fingerprint_does_not_hide_bounds(self):
        issues = self.check(SourceProofSelection(proof_fingerprint="0" * 64, dependency_indices=(0, 3)))
        self.assertEqual(tuple(i.code for i in issues),
            (SourceLogicCode.SELECTION_PROOF_MISMATCH, SourceLogicCode.SELECTION_OUT_OF_RANGE))
        self.assertTrue(all(i.group_index == 3 and i.use_index is None for i in issues))
        self.assertEqual(self.check(SourceProofSelection(proof_fingerprint=fingerprint(self.proof),
            dependency_indices=(0,))), ())

    def test_invalid_indices_keep_original_paths_and_independent_bounds(self):
        selection = SourceProofSelection.model_construct(proof_fingerprint="0" * 64,
            dependency_indices=(True, -1, 2, 2, 0, 9))
        issues = self.check(selection)
        self.assertEqual(tuple(i.code for i in issues), (SourceFieldCode.INVALID_SELECTION,) * 4 + (
            SourceLogicCode.SELECTION_PROOF_MISMATCH, SourceLogicCode.SELECTION_OUT_OF_RANGE))
        path = selection_path().field(FieldRef(lambda: SourceProofSelection, lambda s: s.dependency_indices))
        self.assertEqual(tuple(i.path for i in issues[:4]), tuple(path.item(i).freeze() for i in (0, 1, 3, 4)))
        self.assertEqual(selection.dependency_indices, (True, -1, 2, 2, 0, 9))

    def test_multiple_bounds_failures_are_one_issue_per_selection(self):
        for group in (None, 3):
            for correct_fingerprint in (True, False):
                with self.subTest(group=group, correct_fingerprint=correct_fingerprint):
                    selection = SourceProofSelection(proof_fingerprint=(fingerprint(self.proof)
                        if correct_fingerprint else "0" * 64), dependency_indices=(4, 5))
                    issues = self.checker.check(selection, proof=self.proof,
                        path=selection_path(), selection_index=group)
                    expected = (() if correct_fingerprint else (SourceLogicCode.SELECTION_PROOF_MISMATCH,))
                    self.assertEqual(tuple(i.code for i in issues), expected + (SourceLogicCode.SELECTION_OUT_OF_RANGE,))
                    self.assertTrue(all(i.group_index == group and i.use_index is None
                        and i.source is None and i.artifact is None for i in issues))
        self.assertEqual(self.check(SourceProofSelection(proof_fingerprint=fingerprint(self.proof),
            dependency_indices=(0,))), ())

    def test_pojo_and_checker_share_shape_and_order_rules(self):
        path = selection_path().field(FieldRef(lambda: SourceProofSelection, lambda s: s.dependency_indices))
        for indices, positions in (((0, 0), (1,)), ((2, 0, 2), (1, 2)),
                ((True, -1, 1.0, "1", 0), (0, 1, 2, 3)), ((2, True, 0, 2), (1, 2, 3))):
            with self.subTest(indices=indices):
                with self.assertRaises(ValidationError):
                    SourceProofSelection(proof_fingerprint=fingerprint(self.proof), dependency_indices=indices)
                forged = SourceProofSelection.model_construct(proof_fingerprint=fingerprint(self.proof),
                    dependency_indices=indices)
                issues = self.check(forged)
                self.assertEqual(tuple(i.code for i in issues), (SourceFieldCode.INVALID_SELECTION,) * len(positions))
                self.assertEqual(tuple(i.path for i in issues), tuple(path.item(i).freeze() for i in positions))
