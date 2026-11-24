"""Admission stays pure and preserves exact owning facts before encoding."""
import unittest
from unittest.mock import patch
from typing import Annotated
from pydantic import Field, TypeAdapter
from app.dataModel.patch.validation.admissionCode import PatchSetAdmissionCode
from pydantic import ValidationError, model_validator
from app.application.patch.encoding.patchSetCodec import PatchSetCodec
from app.application.patch.contracts.sectionHandler import SectionContract
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.patch.errors import PatchSetAdmissionError, PatchSetValidationClassificationError
from app.application.patch.validation.modelValidationErrors import PatchSetModelValidationErrors
from app.dataModel.patch.validation.admissionReasons import (
    PatchSetRequestVersionUnsupported, PatchSetSectionKeyUnknown, PatchSetStructuralFailure,
    PatchSetSectionModelMismatch, PatchSetSectionVersionUnsupported, PatchSetCompatibilityIssue,
)
from app.dataModel.patch.validation.patchSetInvariants import PatchSetInvariants
from app.dataModel.patch.validation.invariantViolation import PatchSetInvariantViolation
from app.dataModel.patch.validation.structuralErrorKind import PatchSetStructuralErrorKind
from app.dataModel.patch.request.patchSet import PatchSet
from tests.snapshotCore.support.fakeSection import (
    FakeSection, FakePatchSet, FakeSectionRefused, FakeSectionHandler, FakeSectionCodec,
    FAKE_SECTION_SCHEMA, FakePatch, FakeTarget, FakeChange, FakePrepared,
)
from tests.snapshotCore.contracts.test_patch_invariants import values, section


class AdmissionTests(unittest.TestCase):
    def test_compatibility_codes_preserve_wire_and_discriminator(self):
        from app.dataModel.fields.validatedFieldPath import ModelIdentity
        adapter = TypeAdapter(Annotated[PatchSetCompatibilityIssue, Field(discriminator="code")])
        cases = (
            (PatchSetRequestVersionUnsupported, PatchSetAdmissionCode.REQUEST_VERSION_UNSUPPORTED,
             dict(actual_version=2, supported_versions=(1,))),
            (PatchSetSectionKeyUnknown, PatchSetAdmissionCode.SECTION_KEY_UNKNOWN,
             dict(section_index=0, section_key="x")),
            (PatchSetSectionModelMismatch, PatchSetAdmissionCode.SECTION_MODEL_MISMATCH,
             dict(section_index=0, section_key="x", expected_model=ModelIdentity.of(FakeSection),
                  actual_type_name="wrong.Model")),
            (PatchSetSectionVersionUnsupported, PatchSetAdmissionCode.SECTION_VERSION_UNSUPPORTED,
             dict(section_index=0, section_key="x", actual_version=2, supported_versions=(1,))),
        )
        for model, code, fields in cases:
            with self.subTest(code=code):
                fact = model(code=code, **fields)
                self.assertIs(fact.code, code)
                self.assertEqual(fact.model_dump(mode="json")["code"], code.value)
                restored = adapter.validate_json(fact.model_dump_json(), strict=True)
                self.assertIs(type(restored), model)
                self.assertIs(restored.code, code)
                self.assertEqual(restored, fact)
                with self.assertRaises(ValidationError):
                    model(code="patch_set.admission.unknown", **fields)

    def test_structural_fact_rejects_unknown_error_type(self):
        with self.assertRaises(ValidationError):
            PatchSetStructuralFailure.model_validate({
                "error_type": "invented_error", "loc": (), "message": "invalid"})

    def setUp(self):
        self.registry = SectionRegistry(FakeSectionRefused)
        contract = SectionContract(key="x", section_model=FakeSection,
            supported_versions=frozenset({1}), manifest=FAKE_SECTION_SCHEMA)
        self.handler = FakeSectionHandler(contract)
        self.encoder = FakeSectionCodec(contract)
        self.registry.register(contract, self.handler, self.encoder)
        self.codec = PatchSetCodec(self.registry, FakePatchSet)
        source = section("x")
        native = FakeSection(header=source.header, patches=(FakePatch(header=source.patches[0].header,
            target=FakeTarget(name="x"), change=FakeChange(amount=1), prepared=FakePrepared(values=(1,))),))
        self.request = FakePatchSet(**values((native,)))

    def test_core_facts_survive_once_with_indices_and_cause(self):
        bad = self.request.model_copy(update={"world_uid": "wrong"})
        with patch.object(PatchSetInvariants, "check_core", wraps=PatchSetInvariants.check_core) as core:
            with self.assertRaises(PatchSetAdmissionError) as caught:
                self.codec.validate_request(bad)
            self.assertEqual(core.call_count, 1)
        self.assertIs(type(caught.exception.reasons[0]), PatchSetInvariantViolation)
        self.assertIsInstance(caught.exception.__cause__, ValidationError)
        self.assertEqual(self.encoder.calls, [])

    def test_independent_request_and_section_compatibility_aggregate(self):
        native = self.request.sections[0]
        native = native.model_copy(update={"header": native.header.model_copy(update={"key": "unknown"}),
            "patches": (native.patches[0].model_copy(update={"header": native.patches[0].header.model_copy(
                update={"ref": native.patches[0].header.ref.model_copy(update={"section_key": "unknown"})})}),)})
        bad = self.request.model_copy(update={"format_version": 2, "sections": (native,)})
        with self.assertRaises(PatchSetAdmissionError) as caught:
            self.codec.encode(bad)
        self.assertEqual(tuple(map(type, caught.exception.reasons)),
                         (PatchSetRequestVersionUnsupported, PatchSetSectionKeyUnknown))
        self.assertEqual(caught.exception.reasons[1].section_index, 0)
        self.assertIs(caught.exception.reasons[0].code, PatchSetAdmissionCode.REQUEST_VERSION_UNSUPPORTED)
        self.assertIs(caught.exception.reasons[1].code, PatchSetAdmissionCode.SECTION_KEY_UNKNOWN)
        self.assertEqual(self.encoder.calls, [])
        self.assertEqual(self.handler.calls, [])

    def test_root_locations_preserved_without_prefix(self):
        native = self.request.sections[0]
        bad_patch = native.patches[0].model_copy(update={"prepared": FakePrepared.model_construct(values="bad")})
        bad = self.request.model_copy(update={"sections": (native.model_copy(update={"patches": (bad_patch,)}),)})
        with self.assertRaises(PatchSetAdmissionError) as caught:
            self.codec.validate_request(bad)
        fact = caught.exception.reasons[0]
        self.assertIs(type(fact), PatchSetStructuralFailure)
        self.assertIs(fact.error_type, PatchSetStructuralErrorKind.TUPLE_TYPE)
        self.assertEqual(PatchSetStructuralFailure.model_validate_json(fact.model_dump_json()), fact)
        self.assertEqual(fact.loc, ("sections", 0, "patches", 0, "prepared", "values"))

    def test_unknown_validator_exception_is_not_structural(self):
        error = ValidationError.from_exception_data("request", [{"type": "value_error", "loc": (),
            "input": None, "ctx": {"error": ValueError("unclassified")}}])
        with self.assertRaises(PatchSetValidationClassificationError) as caught:
            PatchSetModelValidationErrors.classify(error)
        self.assertIs(caught.exception.__cause__, error)

    def test_construction_and_wrong_exact_request(self):
        class ChangedMode(FakePatchSet):
            coherent_request = model_validator(mode="before")(PatchSet.coherent_request)
        with self.assertRaises(TypeError):
            PatchSetCodec(self.registry, ChangedMode)
        with self.assertRaises(TypeError):
            PatchSetCodec(self.registry, PatchSet[FakeSection])
        with self.assertRaises(ValueError):
            PatchSetCodec(SectionRegistry(FakeSectionRefused), FakePatchSet)
        with self.assertRaises(PatchSetAdmissionError):
            self.codec.validate_request(object())
        self.assertEqual(self.registry.section_models, frozenset({FakeSection}))

    def test_encode_fault_not_input_refusal_and_success_roundtrip(self):
        checked = self.codec.validate_request(self.request)
        self.assertEqual(checked, self.request)
        self.assertEqual(self.encoder.calls, [])
        self.assertEqual(self.codec.decode(self.codec.encode(checked)), checked)
        fault = ValueError("encoder execution")
        with patch.object(self.encoder, "encode", side_effect=fault):
            with self.assertRaises(ValueError) as caught:
                self.codec.fingerprint(checked)
        self.assertIs(caught.exception, fault)
