"""Owning envelope/codec identity, independent of Engine transport and storage IO."""

import unittest
from unittest.mock import create_autospec

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.application.artifacts.contracts.formatBackend import ArtifactBackend, ArtifactFormatContract
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.staging.artifactDescriptor import ArtifactDescriptorBuilder
from app.application.artifacts.staging.artifactInputAdmission import ArtifactInputAdmission
from app.application.artifacts.staging.artifactOpenPipeline import ArtifactPrepareStageOpenPipeline
from app.application.artifacts.staging.stageErrors import ArtifactInputRejected
from app.dataModel.artifacts.staging.inputErrors import ArtifactInputError, ArtifactInputIssue, ArtifactInputIssueCode
from app.dataModel.artifacts.staging.preparedArtifact import ArtifactPrepareStageInputBase, PreparedArtifactBase
from app.dataModel.artifacts.staging.stageInput import ArtifactStageInputBase
from app.dataModel.fields.validatedFieldPath import ModelIdentity, FieldSegment, ValidatedFieldPath
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, RegisteredTypeEntry, CanonicalTypeKind
from app.encoding.canonicalCodec import CanonicalCodec, CanonicalEncodingError, decode
from app.dataModel.artifacts.references import ArtifactKind, ArtifactFormatRegistry
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.staging.preparedArtifact import ArtifactPrepareStageInput, PreparedArtifact
from app.dataModel.artifacts.staging.stageInput import ArtifactStageInput
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.registryKey import RegistryKey
from tests.snapshotCore.support.fakeSection import FakePrepared


class ChildPrepared(FakePrepared):
    pass


class Normalizing(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    text: str

    @field_validator("text")
    @classmethod
    def trim(cls, value: str) -> str:
        return value.strip()


class TrustedChild(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="never")
    count: int


class NestedContent(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    child: TrustedChild


class MutatingContent(NestedContent):
    @field_validator("child")
    @classmethod
    def mutate_child(cls, value: TrustedChild) -> TrustedChild:
        object.__setattr__(value, "count", value.count + 1)
        return value


class DiagnosticWrapper(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    error: ArtifactInputError


class ContentIdentityTests(unittest.TestCase):
    def test_diagnostic_schema_paths_and_full_transport(self):
        content = FakePrepared(values=(1,))
        contract = ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry]("test.rows"),
            kind=ArtifactKind.SQL_ROWS, supported_versions=frozenset({1}), content_model=FakePrepared,
            encode=lambda value: value.model_dump_json().encode(), decode=lambda data, version: content,
            row_count=lambda value: len(value.values))
        backend = create_autospec(ArtifactBackend, instance=True)
        backend.contract = contract
        registry = ArtifactFormatRegistryBinding()
        registry.register(contract, backend)
        builder = ArtifactDescriptorBuilder(contract, 1, registry)
        admission = ArtifactInputAdmission(contract)
        request = ArtifactPrepareStageInput[FakePrepared](content=content)
        self.assertIs(admission.prepare(request), request)
        with self.assertRaises(ArtifactInputRejected) as caught:
            admission.prepare(request.model_copy(update={"content": b"wrong"}))
        prepare_error = caught.exception.error
        self.assertEqual(prepare_error.issues[0].path.root, ModelIdentity.of(ArtifactPrepareStageInputBase))
        self.assertEqual(prepare_error.issues[0].path.projection(), ("content",))
        self.assertEqual(prepare_error.issues[0].path.segments[0].owner, ModelIdentity.of(ArtifactPrepareStageInputBase))
        prepared = builder.prepare(content)
        lease = OperationLeaseRef(operation_id="diagnostics", world_uid="world",
            kind=OperationKind.PACK_ACTIVATION, preparation_fingerprint="0" * 64, fence=1)
        stage = ArtifactStageInput[FakePrepared](lease=lease, prepared=prepared)
        self.assertIs(admission.stage(stage), stage)
        self.assertIs(stage.prepared, prepared)
        self.assertIs(prepared.content, content)
        wrong = prepared.model_copy(update={"content": b"wrong", "descriptor":
            prepared.descriptor.model_copy(update={"format_version": 2})})
        with self.assertRaises(ArtifactInputRejected) as caught:
            admission.stage(stage.model_copy(update={"prepared": wrong}))
        error = caught.exception.error
        self.assertEqual(tuple(issue.code for issue in error.issues),
            (ArtifactInputIssueCode.CONTENT_TYPE_MISMATCH, ArtifactInputIssueCode.FORMAT_BINDING_MISMATCH))
        self.assertEqual(tuple(issue.path.projection() for issue in error.issues),
            (("prepared", "content"), ("prepared",)))
        for issue in error.issues:
            self.assertEqual(issue.path.root, ModelIdentity.of(ArtifactStageInputBase))
            self.assertEqual(issue.path.segments[0].owner, ModelIdentity.of(ArtifactStageInputBase))
        self.assertEqual(error.issues[0].path.segments[1].owner, ModelIdentity.of(PreparedArtifactBase))
        with self.assertRaises(ArtifactInputRejected) as caught:
            builder.check(prepared.model_copy(update={"descriptor":
                prepared.descriptor.model_copy(update={"nbytes": prepared.descriptor.nbytes + 1})}))
        descriptor_error = caught.exception.error
        path = descriptor_error.issues[0].path
        self.assertEqual(descriptor_error.issues[0].code, ArtifactInputIssueCode.DESCRIPTOR_MISMATCH)
        self.assertEqual(path.root, ModelIdentity.of(ArtifactStageInputBase))
        self.assertEqual(path.projection(), ("prepared", "descriptor"))
        self.assertEqual(tuple(segment.owner for segment in path.segments),
            (ModelIdentity.of(ArtifactStageInputBase), ModelIdentity.of(PreparedArtifactBase)))
        # Test-local allowlist proves cold diagnostic transport, not production IDs.
        models = (ArtifactPrepareStageInputBase, PreparedArtifactBase, ArtifactStageInputBase,
            DiagnosticWrapper, ArtifactInputError, ArtifactInputIssue, ValidatedFieldPath, FieldSegment, ModelIdentity)
        manifest = CanonicalSchemaManifest(entries=tuple(RegisteredTypeEntry(type_id=index,
            python_type=model, kind=CanonicalTypeKind.RECORD) for index, model in enumerate(models, 1)) +
            (RegisteredTypeEntry(type_id=100, python_type=ArtifactInputIssueCode, kind=CanonicalTypeKind.ENUM),))
        for value in (prepare_error, error, descriptor_error):
            wrapped = DiagnosticWrapper(error=value)
            self.assertEqual(wrapped.error, value)
            self.assertEqual(DiagnosticWrapper.model_validate(wrapped.model_dump()).error, value)
            self.assertEqual(DiagnosticWrapper.model_validate_json(wrapped.model_dump_json()).error, value)
            encoded = CanonicalCodec(manifest).encode(wrapped)
            self.assertEqual(decode(encoded, DiagnosticWrapper, manifest), wrapped)
            missing_roots = CanonicalSchemaManifest(entries=tuple(entry for entry in manifest.entries
                if entry.python_type not in (ArtifactPrepareStageInputBase, PreparedArtifactBase, ArtifactStageInputBase)))
            with self.assertRaises(CanonicalEncodingError):
                decode(encoded, DiagnosticWrapper, missing_roots)
        backend.write.assert_not_called()

    def test_stage_rejects_forged_prepared_without_replacing_valid_instance(self):
        ref = ArtifactRef(kind=ArtifactKind.SQL_ROWS,
            format_key=RegistryKey[ArtifactFormatRegistry]("test.rows"), format_version=1,
            content_hash="0" * 64, nbytes=0, row_count=1)
        content = FakePrepared(values=(1,))
        prepared = PreparedArtifact[FakePrepared](content=content, descriptor=ref)
        lease = OperationLeaseRef(operation_id="identity", world_uid="world",
            kind=OperationKind.PACK_ACTIVATION, preparation_fingerprint="0" * 64, fence=1)
        for fields in ({"content": content.model_copy(update={"values": ("bad",)})},
                       {"content": content.model_copy(update={"values": [1]})},
                       {"descriptor": ref.model_copy(update={"nbytes": -1})}):
            forged = prepared.model_copy(update=fields)
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                ArtifactStageInput[FakePrepared](lease=lease, prepared=forged)
        stage = ArtifactStageInput[FakePrepared](lease=lease, prepared=prepared)
        self.assertIs(stage.prepared, prepared)
        self.assertIs(stage.prepared.content, content)

    def test_mutating_validator_cannot_modify_original_graph(self):
        content = MutatingContent(child=TrustedChild(count=0))
        self.assertEqual(content.child.count, 1)
        with self.assertRaises(ValidationError):
            ArtifactPrepareStageInput[MutatingContent](content=content)
        self.assertEqual(content.child.count, 1)
        binding = ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry]("test.mutating"),
            kind=ArtifactKind.SQL_ROWS, supported_versions=frozenset({1}), content_model=MutatingContent,
            encode=lambda value: b"unused", decode=lambda data, version: content, row_count=lambda value: 1)
        backend = create_autospec(ArtifactBackend, instance=True)
        backend.contract = binding
        registry = ArtifactFormatRegistryBinding()
        registry.register(binding, backend)
        with self.assertRaises(ValueError):
            registry.encode(binding, content)
        self.assertEqual(content.child.count, 1)

    def test_prepared_negatives_and_nested_trusted_schema(self):
        ref = ArtifactRef(kind=ArtifactKind.SQL_ROWS,
            format_key=RegistryKey[ArtifactFormatRegistry]("test.rows"), format_version=1,
            content_hash="0" * 64, nbytes=0, row_count=1)
        bad = FakePrepared(values=(1,)).model_copy(update={"values": ("bad",)})
        with self.assertRaises(ValidationError):
            PreparedArtifact[FakePrepared](content=bad, descriptor=ref)
        child = TrustedChild(count=1).model_copy(update={"count": "bad"})
        content = NestedContent(child=child)
        with self.assertRaises(ValidationError):
            ArtifactPrepareStageInput[NestedContent](content=content)
        self.assertIn("content", ArtifactPrepareStageInput[FakePrepared].model_json_schema()["properties"])

    def test_full_owning_path(self):
        for model, content, kind in ((FakePrepared, FakePrepared(values=(1, 2)), ArtifactKind.SQL_ROWS),
                                     (bytes, bytes(bytearray(b"payload")), ArtifactKind.BLOB)):
            with self.subTest(model=model):
                seen = []

                def encode(value):
                    seen.append(value)
                    return value if model is bytes else value.model_dump_json().encode()

                contract = ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry](
                    "test.rows" if model is FakePrepared else "test.blob"), kind=kind,
                    supported_versions=frozenset({1}), content_model=model, encode=encode,
                    decode=lambda data, version: data,
                    row_count=None if model is bytes else lambda value: len(value.values))
                backend = create_autospec(ArtifactBackend, instance=True)
                backend.contract = contract
                registry = ArtifactFormatRegistryBinding()
                registry.register(contract, backend)
                builder = ArtifactDescriptorBuilder(contract, 1, registry)
                request = ArtifactPrepareStageInput[model](content=content)
                result = ArtifactPrepareStageOpenPipeline(ArtifactInputAdmission(contract), builder).prepare_stage(request)
                self.assertIs(request.content, content)
                self.assertIs(result.content, content)
                self.assertIs(seen[0], content)
                lease = OperationLeaseRef(operation_id="identity", world_uid="world",
                    kind=OperationKind.PACK_ACTIVATION, preparation_fingerprint="0" * 64, fence=1)
                stage = ArtifactStageInput[model](lease=lease, prepared=result)
                self.assertIs(stage.prepared, result)
                self.assertIs(stage.prepared.content, content)
                restored = type(stage).model_validate_json(stage.model_dump_json(), strict=True)
                self.assertEqual(restored, stage)
                self.assertIsNot(restored.prepared, result)
                backend.write.assert_not_called()

    def test_native_json_tuple_and_strict_python(self):
        model = ArtifactPrepareStageInput[FakePrepared]
        self.assertEqual(model.model_validate_json('{"content":{"values":[1,2]}}', strict=True).content.values, (1, 2))
        with self.assertRaises(ValidationError):
            model.model_validate({"content": {"values": [1, 2]}}, strict=True)
        with self.assertRaises(ValidationError):
            model.model_validate_json('{"content":{"values":["1"]}}', strict=True)

    def test_wrong_concrete_and_subclass(self):
        for value in (b"wrong", ChildPrepared(values=(1,))):
            with self.subTest(value=type(value)), self.assertRaises(ValidationError):
                ArtifactPrepareStageInput[FakePrepared](content=value)

    def test_forged_invalid_mutable_missing_and_normalizing(self):
        for values in (("bad",), [1, 2]):
            forged = FakePrepared(values=(1,)).model_copy(update={"values": values})
            with self.subTest(values=values), self.assertRaises(ValidationError):
                ArtifactPrepareStageInput[FakePrepared](content=forged)
        missing = FakePrepared(values=(1,)).model_copy()
        del missing.__dict__["values"]
        with self.assertRaises(ValidationError):
            ArtifactPrepareStageInput[FakePrepared](content=missing)
        noncanonical = Normalizing(text="ok").model_copy(update={"text": " spaced "})
        with self.assertRaises(ValidationError):
            ArtifactPrepareStageInput[Normalizing](content=noncanonical)


if __name__ == "__main__":
    unittest.main()
