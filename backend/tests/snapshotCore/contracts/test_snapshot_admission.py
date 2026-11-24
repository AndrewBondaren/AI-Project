"""Snapshot admission with real owning codec and explicit mocked claim boundary."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError

from app.application.patch.encoding.patchSetCodec import PatchSetCodec
from app.application.patch.contracts.sectionHandler import SectionContract
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.patch.errors import PatchSetAdmissionError, PatchSetValidationClassificationError
from app.application.worldSnapshot.errors import SnapshotPublicError
from app.application.worldSnapshot.service.worldSnapshotService import WorldSnapshotService
from app.application.worldSnapshot.validation.publicInputValidation import SnapshotPublicInputValidation
from app.dataModel.patch.validation.admissionReasons import (
    PatchSetRequestVersionUnsupported, PatchSetSectionKeyUnknown, PatchSetSectionModelMismatch,
    PatchSetSectionVersionUnsupported, PatchSetStructuralFailure,
)
from app.dataModel.fields.validatedFieldPath import ModelIdentity
from app.dataModel.patch.validation.structuralErrorKind import PatchSetStructuralErrorKind
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.patch.validation.patchSetInvariants import PatchSetInvariants
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation
from app.dataModel.patch.validation.invariantDetails import (
    WorldMismatchDetails, MissingPackDetails, DuplicatePlayerDetails, DuplicateSectionDetails,
    MissingPreparedDependencyDetails, PreparedDependencyOrderDetails, PatchOperationMismatchDetails,
    PatchSectionMismatchDetails, DuplicatePatchOrdinalDetails,
)
from app.dataModel.worldSnapshot.errors.publicFault import (
    SnapshotPublicFault, SnapshotPublicFailureKind as Kind, SnapshotPublicOperation,
)
from tests.snapshotCore.support.fakeSection import (
    FakeSection, FakePatchSet, FakeSectionRefused, FakeSectionHandler, FakeSectionCodec, FAKE_SECTION_SCHEMA,
    FakePatch, FakeTarget, FakeChange, FakePrepared,
)
from tests.snapshotCore.support.publicationBinding import TEST_PUBLICATION_BINDING
from tests.snapshotCore.contracts.test_patch_invariants import values, section
from tests.snapshotCore.support.fixtures import run_async
from tests.errorContracts.test_tagged_paths import MockRequest


class SnapshotAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.registry = SectionRegistry(FakeSectionRefused)
        contract = SectionContract(key="x", section_model=FakeSection,
            supported_versions=frozenset({1}), manifest=FAKE_SECTION_SCHEMA)
        self.registry.register(contract, FakeSectionHandler(contract), FakeSectionCodec(contract))
        self.codec = PatchSetCodec(self.registry, FakePatchSet)
        self.operations = SimpleNamespace(result_binding=TEST_PUBLICATION_BINDING,
            record_model=TEST_PUBLICATION_BINDING.record_model, record_refusal=AsyncMock())
        self.service = WorldSnapshotService(self.registry, None, None, None,
            publication_binding=TEST_PUBLICATION_BINDING, operations=self.operations, request_codec=self.codec)
        self.service._claim_publication = AsyncMock(return_value="claim sentinel")
        self.request = FakePatchSet(**values())

    def fault(self, request):
        with self.assertRaises(SnapshotPublicError) as caught:
            run_async(self.service._admit_and_claim(request))
        self.service._claim_publication.assert_not_awaited()
        self.operations.record_refusal.assert_not_awaited()
        self.assertIsNone(caught.exception.fault.operation_id)
        self.assertIsNone(caught.exception.fault.request_fingerprint)
        return caught.exception

    def test_wrong_class_and_structural_input_stop_before_hash(self):
        for request in ({}, self.request.model_copy(update={"turn_id": "bad"})):
            with patch.object(PatchSetCodec, "fingerprint", side_effect=AssertionError("hash before admission")):
                error = self.fault(request)
            self.assertIs(error.fault.kind, Kind.INVALID_INPUT)

    def test_core_fact_is_preserved_once(self):
        with patch.object(PatchSetInvariants, "check_core", wraps=PatchSetInvariants.check_core) as core:
            error = self.fault(self.request.model_copy(update={"world_uid": "other"}))
            self.assertEqual(core.call_count, 1)
        self.assertIs(error.fault.kind, Kind.ADMISSION_REFUSED)
        self.assertIsInstance(error.__cause__, PatchSetAdmissionError)
        self.assertIsInstance(error.__cause__.__cause__, ValidationError)
        self.assertEqual(error.fault.input_issues[0].details.actual_world_uid, "world")

    def test_mixed_facts_roundtrip_with_all_compatibility_branches(self):
        reasons = (
            PatchSetSectionKeyUnknown(code="patch_set.admission.section_key_unknown", section_index=3, section_key="x"),
            PatchSetStructuralFailure(error_type=PatchSetStructuralErrorKind.INT_TYPE, loc=("turn_id",), message="Input should be a valid integer"),
            PatchSetSectionModelMismatch(code="patch_set.admission.section_model_mismatch", section_index=4,
                section_key="x", expected_model=ModelIdentity.of(FakeSection), actual_type_name="mock.Other"),
            PatchSetRequestVersionUnsupported(code="patch_set.admission.request_version_unsupported",
                actual_version=2, supported_versions=(1,)),
            PatchSetSectionVersionUnsupported(code="patch_set.admission.section_version_unsupported",
                section_index=5, section_key="x", actual_version=3, supported_versions=(1, 2)),
        )
        with patch.object(PatchSetCodec, "validate_request", side_effect=PatchSetAdmissionError(reasons)):
            fault = self.fault(self.request).fault
        restored = SnapshotPublicFault.model_validate_json(fault.model_dump_json())
        self.assertEqual(restored, fault)
        self.assertEqual(tuple(map(type, restored.input_issues)), tuple(map(type, fault.input_issues)))
        self.assertEqual([restored.input_issues[i].section_index for i in (0, 2, 4)], [3, 4, 5])
        for changes in ({"operation_id": "op"}, {"operation_id": "op", "request_fingerprint": "a" * 64},
                        {"kind": Kind.INVALID_INPUT}, {"input_issues": ()}):
            with self.assertRaises(ValidationError):
                SnapshotPublicFault.model_validate(fault.model_copy(update=changes))

    def test_success_passes_exact_hash_and_identity_without_new_attempt(self):
        result = run_async(self.service._admit_and_claim(self.request))
        self.assertEqual(result, "claim sentinel")
        self.service._claim_publication.assert_awaited_once_with(self.request.operation_id, self.request.world_uid,
            self.request.preparation_fingerprint, self.codec.fingerprint(self.request))
        self.operations.record_refusal.assert_not_awaited()

    def test_encoder_fault_is_infrastructure_and_classification_is_not_input(self):
        failure = ValueError("encoder fault")
        with patch.object(PatchSetCodec, "fingerprint", side_effect=failure):
            error = self.fault(self.request)
        self.assertIs(error.fault.kind, Kind.INFRASTRUCTURE_FAILURE)
        self.assertIs(error.__cause__, failure)
        with patch.object(PatchSetCodec, "validate_request", side_effect=PatchSetValidationClassificationError):
            error = self.fault(self.request)
        self.assertIs(error.fault.kind, Kind.INFRASTRUCTURE_FAILURE)
        self.assertIsInstance(error.__cause__, PatchSetValidationClassificationError)

    def test_mapper_consumes_root_fact_without_revalidation_or_prefix(self):
        fact = PatchSetStructuralFailure(error_type=PatchSetStructuralErrorKind.INT_TYPE,
            loc=("sections", 2, "payload", "cat", "years"), message="Input should be a valid integer")
        issue, = SnapshotPublicInputValidation.map_structural(fact, model=MockRequest)
        self.assertEqual(issue.wire_path, ("sections", 2, "payload", "years"))
        self.assertEqual(issue.path.projection(), ("sections", 2, "payload", "age"))
        fault = SnapshotPublicFault(operation=SnapshotPublicOperation.APPLY, kind=Kind.INVALID_INPUT,
            operation_id=None, request_fingerprint=None, input_issues=(issue,))
        restored = SnapshotPublicFault.model_validate_json(fault.model_dump_json())
        self.assertEqual(restored, fault)
        self.assertIs(type(restored.input_issues[0]), type(issue))
        with self.assertRaises(ValidationError):
            SnapshotPublicFault.model_validate({**fault.model_dump(), "input_issues": [issue]})

    def test_structural_enum_roster_has_presentation_without_string_fallback(self):
        for kind in PatchSetStructuralErrorKind:
            with self.subTest(kind=kind):
                fact = PatchSetStructuralFailure(error_type=kind, loc=("turn_id",), message="invalid value")
                issue, = SnapshotPublicInputValidation.map_structural(fact, model=FakePatchSet)
                self.assertEqual(issue.pydantic_type, None if kind is PatchSetStructuralErrorKind.ENUM else kind.value)
                self.assertIs(issue.code, JsonValidationCode.UNKNOWN_ENUM if kind is PatchSetStructuralErrorKind.ENUM
                              else JsonValidationCode.SCHEMA_VIOLATION)
        for raw in ("int_type", "unknown_kind"):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                SnapshotPublicInputValidation.map_structural(fact.model_copy(update={"error_type": raw}),
                                                            model=FakePatchSet)

    def test_foreign_registry_is_constructor_error(self):
        with self.assertRaises(ValueError):
            WorldSnapshotService(SectionRegistry(FakeSectionRefused), None, None, None,
                publication_binding=TEST_PUBLICATION_BINDING, operations=self.operations, request_codec=self.codec)

    def test_prepared_order_refusal_precedes_hash_and_preserves_indices(self):
        source = section("x", dependencies=("missing",))
        native = FakeSection(header=source.header, patches=(FakePatch(header=source.patches[0].header,
            target=FakeTarget(name="x"), change=FakeChange(amount=1), prepared=FakePrepared(values=())),))
        request = FakePatchSet(**values((native,)))
        with patch.object(PatchSetCodec, "fingerprint", side_effect=AssertionError("hash before order check")):
            error = self.fault(request)
        issue, = error.fault.input_issues
        self.assertIs(type(issue), PatchSetInvariantViolation)
        self.assertEqual((issue.section_index, issue.dependency_index, issue.related_index), (0, 0, None))

    def test_all_invariant_details_survive_public_json(self):
        ref = section("x").patches[0].header.ref
        branches = (
            (WorldMismatchDetails(expected_world_uid="w", actual_world_uid="other"), {}),
            (MissingPackDetails(publication=self.request.expected_world), {}),
            (DuplicatePlayerDetails(player_uid="p"), {"player_index": 2, "related_index": 0}),
            (DuplicateSectionDetails(section_key="x"), {"section_index": 3, "related_index": 1}),
            (MissingPreparedDependencyDetails(source_section_key="x", missing_section_key="y"),
                {"section_index": 3, "dependency_index": 2}),
            (PreparedDependencyOrderDetails(source_section_key="x", dependency_section_key="y"),
                {"section_index": 3, "dependency_index": 2, "related_index": 4}),
            (PatchOperationMismatchDetails(patch_ref=ref, expected_operation_id="other"),
                {"section_index": 3, "patch_index": 2}),
            (PatchSectionMismatchDetails(patch_ref=ref, expected_section_key="y"),
                {"section_index": 3, "patch_index": 2}),
            (DuplicatePatchOrdinalDetails(section_key="x", ordinal=0),
                {"section_index": 3, "patch_index": 2, "related_index": 0}),
        )
        reasons = tuple(PatchSetInvariantViolation(details=details, **indices) for details, indices in branches)
        with patch.object(PatchSetCodec, "validate_request", side_effect=PatchSetAdmissionError(reasons)):
            fault = self.fault(self.request).fault
        restored = SnapshotPublicFault.model_validate_json(fault.model_dump_json())
        self.assertEqual(restored, fault)
        self.assertEqual(tuple(type(issue.details) for issue in restored.input_issues),
                         tuple(type(details) for details, _ in branches))

    def test_public_fault_rejects_foreign_subclass_before_union_downcast(self):
        class ForeignIssue(PatchSetSectionKeyUnknown):
            pass
        reason = PatchSetSectionKeyUnknown(code="patch_set.admission.section_key_unknown", section_index=0, section_key="x")
        with patch.object(PatchSetCodec, "validate_request", side_effect=PatchSetAdmissionError((reason,))):
            fault = self.fault(self.request).fault
        with self.assertRaises(ValidationError):
            SnapshotPublicFault.model_validate(fault.model_copy(update={
                "input_issues": (ForeignIssue(**reason.model_dump()),)}))
