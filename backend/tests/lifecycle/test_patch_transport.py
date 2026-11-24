"""Native mixed-section representation through the checked PatchSet registry."""
import unittest

from app.application.patch.contracts.sectionHandler import DomainSectionHandler
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.patch.encoding.sectionFingerprint import SectionFingerprint
from app.application.lifecycle.publication.sectionCodec import LifecycleSectionCodec
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import LifecycleSectionPipelineOpenPipeline
from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyIssue
from app.encoding.canonicalCodec import content_digest, merge_manifests
from tests.lifecycle.support.mixedContracts import LifecycleSectionAB
from tests.lifecycle.support.manifest import MOCK_NATIVE_MANIFEST
from tests.lifecycle.support.snapshotContracts import MockLifecycleSectionRefused, MockSectionRefused
from tests.lifecycle.test_section import mixed_request, section_binding


class RepresentationOnlyHandler(DomainSectionHandler[LifecycleSectionAB, LifecycleApplyIssue]):
    def __init__(self, contract):
        self._contract = contract

    @property
    def contract(self):
        return self._contract

    @property
    def refusal_model(self):
        return MockLifecycleSectionRefused

    async def validate(self, section, context):
        raise AssertionError("representation must not invoke semantics")

    async def apply(self, section, context):
        raise AssertionError("representation must not apply")


class PatchTransportTests(unittest.TestCase):
    def test_terminal_root_roundtrip_preserves_all_diagnostic_branches(self):
        from app.dataModel.fields.checkedPath import CheckedPath
        from app.dataModel.fields.fieldRef import FieldRef
        from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyCode
        from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyCode, SnapshotApplyRelationIssue
        from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
        from app.encoding.canonicalCodec import encode, decode, CanonicalEncodingError
        from tests.lifecycle.support.domainSections import MockSubjectCode, MockSubjectIssue
        from tests.lifecycle.support.snapshotContracts import MockSnapshotApplyResult
        from tests.lifecycle.support.snapshotManifest import MOCK_SNAPSHOT_MANIFEST
        path = CheckedPath.root(LifecycleSectionAB).field(
            FieldRef(lambda: LifecycleSectionAB, lambda section: section.domain_evidence)).freeze()
        issues = (
            LifecycleApplyIssue(code=LifecycleApplyCode.EVIDENCE_MISMATCH, path=path, message="evidence"),
            MockSubjectIssue(code=MockSubjectCode.EFFECT_PAYLOAD_MISMATCH, path=path, message="effect"),
            SnapshotApplyRelationIssue(code=SnapshotApplyCode.DEPENDENCY_MISMATCH,
                                      section_key="mock.lifecycle", player_uid=None, artifact=None),
        )
        result = MockSnapshotApplyResult(category=SnapshotApplyOutcomeKind.REJECTED,
            operation_id="publish", request_fingerprint="a" * 64, committed=None, diagnostics=issues)
        payload = encode(result, MOCK_SNAPSHOT_MANIFEST)
        restored = decode(payload, MockSnapshotApplyResult, MOCK_SNAPSHOT_MANIFEST)
        self.assertIs(type(restored), MockSnapshotApplyResult)
        self.assertEqual(restored, result)
        self.assertEqual(tuple(map(type, restored.diagnostics)), tuple(map(type, issues)))
        self.assertEqual(next(e.type_id for e in MOCK_SNAPSHOT_MANIFEST.entries
                              if e.python_type is MockSnapshotApplyResult), 94001)
        with self.assertRaises(CanonicalEncodingError):
            decode(payload, MockSnapshotApplyResult, MOCK_NATIVE_MANIFEST)

    def test_mixed_native_roundtrip_and_exact_evidence_fingerprint(self):
        binding = section_binding()
        contract = binding.section_contract
        section = LifecycleSectionPipelineOpenPipeline(binding=binding).prepare_section(mixed_request())
        registry = SectionRegistry(MockSectionRefused)
        registry.register(contract, RepresentationOnlyHandler(contract), LifecycleSectionCodec(contract))
        codec = registry.resolve_codec(section)
        payload = codec.encode(section)
        restored = codec.decode(payload, 2)
        self.assertEqual(restored, section)
        self.assertEqual(tuple(map(type, restored.patches)), tuple(map(type, section.patches)))
        self.assertEqual(restored.domain_evidence, section.domain_evidence)
        self.assertEqual(tuple(map(type, restored.domain_evidence)), tuple(map(type, section.domain_evidence)))
        fingerprint = SectionFingerprint(registry)
        self.assertEqual(fingerprint.fingerprint(restored), content_digest(payload).hex())
        changed = section.model_copy(update={"domain_evidence": tuple(reversed(section.domain_evidence))})
        self.assertNotEqual(fingerprint.fingerprint(changed), fingerprint.fingerprint(section))
        for invalid in (
            section.model_copy(update={"patches": ()}),
            section.model_copy(update={"header": section.header.model_copy(update={"format_version": 1})}),
        ):
            with self.assertRaises(ValueError):
                fingerprint.fingerprint(invalid)
        self.assertEqual(merge_manifests(registry.manifest, MOCK_NATIVE_MANIFEST), registry.manifest)
        self.assertNotIn(MockSectionRefused, {entry.python_type for entry in registry.manifest.entries})
