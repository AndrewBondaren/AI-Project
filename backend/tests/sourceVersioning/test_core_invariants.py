"""Pure invariant evidence only, without owning admission or durable authority."""

import unittest

from app.application.worldData.sourceVersioning.proof.validation.sourceProofCanonicalChecker import SourceProofCanonicalChecker
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.sourceVersioning.sourceErrors import SourceFieldCode

from app.application.worldData.sourceVersioning.proof.validation.sourceWorldChecker import SourceWorldChecker
from app.application.worldData.sourceVersioning.proof.validation.sourceUsageConflictChecker import SourceUsageConflictChecker
from app.dataModel.sourceVersioning.sourceErrors import SourceLogicCode
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from tests.sourceVersioning.test_canonical import vector1


class WorldAndConflictTests(unittest.TestCase):
    def test_world_and_empty_context(self):
        checker = SourceWorldChecker()
        self.assertEqual(checker.check("w", expected="w", group_index=None, use_index=None, source=None), ())
        issues = checker.check("other", expected="w", group_index=None, use_index=None, source=None)
        self.assertEqual(issues[0].code, SourceLogicCode.WRONG_WORLD)
        self.assertIsNone(issues[0].use_index)
        with self.assertRaises(ValueError):
            checker.check("w", expected="w", group_index=True, use_index=0, source=None)

    def test_partial_usage_facts_keep_original_positions(self):
        use = vector1().uses[0]
        first = use.dependencies.objects[0]
        second = first.model_copy(update={"revision": SourceRevision(seq=2, content_hash="2" * 64)})
        checker = SourceUsageConflictChecker()
        issues = checker.check(captures=((0, 2, use.capture), (2, 4, use.capture)),
            dependencies=((0, 2, 1, use.capture, first), (2, 4, 3, use.capture, second)))
        self.assertEqual(len(issues), 1)
        self.assertEqual((issues[0].code, issues[0].group_index, issues[0].use_index),
                         (SourceLogicCode.REVISION_CONFLICT, 2, 4))
        self.assertEqual(issues[0].source, second)
        self.assertEqual(checker.check(captures=(), dependencies=()), ())

    def test_repetition_and_historical_capture_are_not_conflicts(self):
        use = vector1().uses[0]
        first = use.dependencies.objects[0]
        second = first.model_copy(update={"revision": SourceRevision(seq=2, content_hash="2" * 64)})
        historical = use.capture.model_copy(update={"artifact": use.capture.artifact.model_copy(
            update={"content_hash": "f" * 64})})
        self.assertEqual(SourceUsageConflictChecker().check(
            captures=((None, 0, use.capture), (None, 1, historical)),
            dependencies=((None, 0, 0, use.capture, first), (None, 0, 1, use.capture, first),
                          (None, 1, 0, historical, second))), ())

    def test_inconsistent_fact_is_programming_error(self):
        use = vector1().uses[0]
        checker = SourceUsageConflictChecker()
        with self.assertRaises(ValueError):
            checker.check(captures=(), dependencies=((None, 0, 0, use.capture, use.dependencies.objects[0]),))
        with self.assertRaises(ValueError):
            checker.check(captures=((None, 0, use.capture), (None, 0, use.capture)), dependencies=())
        with self.assertRaises(ValueError):
            checker.check(captures=((2, 0, use.capture), (1, 0, use.capture)), dependencies=())
        with self.assertRaises(ValueError):
            checker.check(captures=((None, 0, use.capture), (1, 0, use.capture)), dependencies=())


def proof_path():
    return CheckedPath.root(SourceProofReadInput).field(FieldRef(
        lambda: SourceProofReadInput, lambda request: request.proof))


class CanonicalTests(unittest.TestCase):
    def test_valid_and_empty_proofs(self):
        checker = SourceProofCanonicalChecker()
        self.assertEqual(checker.check(vector1(), path=proof_path()), ())
        self.assertEqual(checker.check(SourceDurableProof(schema_version=1, world_uid="w", uses=()),
                                       path=proof_path()), ())

    def test_duplicates_and_empty_use_preserve_paths_and_input(self):
        proof = vector1()
        use = proof.uses[0]
        ref = use.dependencies.objects[0]
        duplicate = SourceCaptureUsage.model_construct(capture=use.capture,
            dependencies=SourceDependencySet(objects=(ref, ref), collections=()))
        empty = SourceCaptureUsage.model_construct(capture=use.capture,
            dependencies=SourceDependencySet(objects=(), collections=()))
        malformed = SourceDurableProof.model_construct(schema_version=1,
            world_uid=proof.world_uid, uses=(duplicate, empty))
        issues = SourceProofCanonicalChecker().check(malformed, path=proof_path())
        self.assertEqual(len(issues), 3)
        self.assertTrue(all(issue.code == SourceFieldCode.NON_CANONICAL_PROOF for issue in issues))
        self.assertEqual(issues[0].path, proof_path().field(FieldRef(
            lambda: SourceDurableProof, lambda p: p.uses)).freeze())
        self.assertEqual(issues[1].path, proof_path().field(FieldRef(lambda: SourceDurableProof,
            lambda p: p.uses)).item(0).field(FieldRef(lambda: SourceCaptureUsage,
            lambda u: u.dependencies)).field(FieldRef(lambda: SourceDependencySet, lambda d: d.objects)).freeze())
        self.assertEqual(malformed.uses, (duplicate, empty))
