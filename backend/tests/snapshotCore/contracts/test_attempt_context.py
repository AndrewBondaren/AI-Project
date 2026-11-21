"""Attempt identity, lifetime and actual section fingerprints; no domain semantics."""
import unittest
from dataclasses import replace

from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.patch.contracts.sectionHandler import SectionContract
from app.application.patch.encoding.sectionFingerprint import SectionFingerprint
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.service.attemptContextBuilder import SnapshotAttemptContextBuilder
from app.application.worldSnapshot.validation.preparedDependencyValidator import SnapshotPreparedDependencyValidator
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.dependency import PreparedSectionDependency
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.registry.sectionMetadata import PatchSectionRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyCode
from tests.snapshotCore.support.fakeSection import (
    FAKE_SECTION_SCHEMA, FakeSection, FakePatch, FakeTarget, FakeChange, FakePrepared,
    FakeSectionHandler, FakeSectionCodec, FakeSectionRefused, HeaderOnlyPatch,
)


class ReadScope:
    active = True

    def assert_active(self):
        if not self.active:
            raise PublicationInfrastructureError("expired read scope")


class AttemptContextTests(unittest.TestCase):
    def setUp(self):
        self.key = RegistryKey[PatchSectionRegistry]("subject")
        self.contract = SectionContract(key=self.key, section_model=FakeSection,
            supported_versions=frozenset({1}), manifest=FAKE_SECTION_SCHEMA)
        self.registry = SectionRegistry(FakeSectionRefused)
        self.registry.register(self.contract, FakeSectionHandler(self.contract), FakeSectionCodec(self.contract))
        self.section = FakeSection(header=SectionHeader(key=self.key, format_version=1, depends_on=()),
            patches=(FakePatch(header=PatchHeader(ref=PatchRef(operation_id="op", section_key=self.key, ordinal=0),
                format_version=1, depends_on=(), artifacts=()), target=FakeTarget(name="subject"),
                change=FakeChange(amount=1), prepared=FakePrepared(values=(1,))),))
        q = WorldPublicationRef(world_uid="w", publication_id="q", snapshot_head=None,
            pack_hash="a" * 64, gameplay_started=True, active_timeline_id="t")
        self.request = PatchSet[FakeSection](format_version=1, operation_id="op", preparation_fingerprint="b" * 64,
            world_uid="w", timeline_id="t", turn_id=1, expected_world=q, expected_players=(), sections=(self.section,))
        self.scope = ReadScope()
        self.builder = SnapshotAttemptContextBuilder(registry=self.registry)

    def test_exact_request_scope_and_same_view(self):
        context = self.builder.build(self.request, scope=self.scope, resolved_dependencies=())
        self.assertIs(context.admitted_sections.require(self.key, model=FakeSection), self.request.sections[0])
        self.builder.assert_bound(context, request=self.request, scope=self.scope)
        with self.assertRaises(PublicationInfrastructureError):
            self.builder.assert_bound(replace(context), request=self.request, scope=self.scope)
        replacement_dependency = PreparedSectionDependency(section_key=self.key, section_fingerprint="c" * 64)
        with self.assertRaises(PublicationInfrastructureError):
            self.builder.assert_bound(replace(context, resolved_dependencies=(replacement_dependency,)),
                request=self.request, scope=self.scope)
        other_builder = SnapshotAttemptContextBuilder(registry=self.registry)
        with self.assertRaises(PublicationInfrastructureError):
            self.builder.assert_bound(other_builder.build(self.request, scope=self.scope, resolved_dependencies=()),
                request=self.request, scope=self.scope)
        for request, scope in ((self.request.model_copy(), self.scope), (self.request, ReadScope())):
            with self.assertRaises(PublicationInfrastructureError):
                self.builder.assert_bound(context, request=request, scope=scope)
        foreign = self.builder.build(self.request.model_copy(), scope=self.scope, resolved_dependencies=())
        with self.assertRaises(PublicationInfrastructureError):
            self.builder.assert_bound(replace(context, admitted_sections=foreign.admitted_sections),
                request=self.request, scope=self.scope)
        self.scope.active = False
        with self.assertRaises(PublicationInfrastructureError):
            context.admitted_sections.require(self.key, model=FakeSection)

    def test_fingerprint_is_actual_subject_bytes_not_request_digest(self):
        fingerprint = SectionFingerprint(self.registry)
        good = fingerprint.fingerprint(self.request.sections[0])
        key = RegistryKey[PatchSectionRegistry]("consumer")
        def request(digest):
            consumer = DomainSection[HeaderOnlyPatch](header=SectionHeader(key=key, format_version=1,
                depends_on=(PreparedSectionDependency(section_key=self.key, section_fingerprint=digest),)),
                patches=(HeaderOnlyPatch(header=PatchHeader(ref=PatchRef(operation_id="op", section_key=key, ordinal=0),
                    format_version=1, depends_on=(), artifacts=())),))
            return PatchSet[FakeSection | type(consumer)](**{
                name: getattr(self.request, name) for name in type(self.request).model_fields if name != "sections"
            }, sections=(self.section, consumer))
        validator = SnapshotPreparedDependencyValidator(fingerprints=fingerprint)
        self.assertEqual(validator.validate(request(good)), ())
        issues = validator.validate(request("0" * 64))
        self.assertEqual(len(issues), 1)
        self.assertEqual((issues[0].code, issues[0].section_key), (SnapshotApplyCode.DEPENDENCY_MISMATCH, key))

    def test_codec_failure_is_not_business_mismatch(self):
        class BrokenFingerprint(SectionFingerprint):
            def fingerprint(self, section):
                raise TypeError("bad codec output")
        self.section = self.section.model_copy(update={"header": self.section.header.model_copy(update={
            "depends_on": (PreparedSectionDependency(section_key=self.key, section_fingerprint="0" * 64),)})})
        request = self.request.model_copy(update={"sections": (self.section,)})
        with self.assertRaises(PublicationInfrastructureError) as caught:
            SnapshotPreparedDependencyValidator(fingerprints=BrokenFingerprint(self.registry)).validate(request)
        self.assertIsInstance(caught.exception.__cause__, TypeError)
