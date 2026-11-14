"""Frozen Source v1 wire contract; fixtures do not assert finalized provenance."""

import subprocess
import sys
import unittest

from pydantic import ValidationError

from app.application.artifacts.encoding.coreManifest import ARTIFACT_CORE_SCHEMA
from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1 as SCHEMA
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.sourceVersioning.sourceBodyVersion import SourceBodyVersion, SourceCollectionVersion
from app.dataModel.sourceVersioning.sourceCapture import SourceCapture
from app.dataModel.sourceVersioning.sourceCaptureRef import SourceCaptureRef
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceCaptureWitness import SourceCaptureWitness
from app.dataModel.sourceVersioning.sourceCollection import SourceCollectionBody
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDescriptor import SourceDescriptorCategory as Category, SourceMemberKey
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceErrors import SourceFailure, SourceLogicCode, SourceLogicIssue, SourceOperation
from app.dataModel.sourceVersioning.sourceObjectId import (
    EntityObjectId, LibraryMemberId, RegistryMemberId, SourceCollectionId, SourceSettingsId,
)
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.sourceVersioning.sourceProofResult import SourceProofResult
from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.sourceVersioning.sourceVersionRef import SourceCollectionVersionRef, SourceVersionRef
from app.dataModel.worldPack.encoding.pinBindings import PACK_PIN_SCHEMA
from app.encoding.canonicalCodec import CanonicalEncodingError, content_digest, decode, encode, merge_manifests


V0_HEX = (
    "07000000000000009708000000000000008e020000000000000004000115db080000000000000078"
    "08000000000000002204000000000000000e736368656d615f76657273696f6e0200000000000000020001"
    "080000000000000025040000000000000009776f726c645f75696404000000000000000a776f726c642d74657374"
    "08000000000000001604000000000000000475736573080000000000000000"
)


def vector1():
    capture = SourceCaptureRef(world_uid="world-test", artifact=ArtifactRef(
        kind=ArtifactKind.SQL_ROWS, format_key=RegistryKey("source.capture-witness"), format_version=1,
        content_hash="0" * 64, nbytes=100, row_count=1))
    source = SourceVersionRef(object_id=RegistryMemberId(
        kind=Category.REGISTRY_MEMBER, world_uid="world-test", descriptor=RegistryKey("SCH-WORLD-TERRAIN/member"),
        member_key=SourceMemberKey("plains")), revision=SourceRevision(seq=1, content_hash="1" * 64))
    return SourceDurableProof(schema_version=1, world_uid="world-test", uses=(SourceCaptureUsage(
        capture=capture, dependencies=SourceDependencySet(objects=(source,), collections=())),))


class SourceCanonicalTests(unittest.TestCase):
    def test_literal_v0_and_v1_vectors(self):
        empty = SourceDurableProof(schema_version=1, world_uid="world-test", uses=())
        wire = encode(empty, SCHEMA)
        self.assertEqual(wire.hex(), V0_HEX)
        self.assertEqual(len(wire), 160)
        self.assertEqual(content_digest(wire).hex(), "753fac72650941d0eb1708e8ae777e2de3bd59c0b8e4278d50dd75cd040267a3")
        value = vector1()
        wire = encode(value, SCHEMA)
        self.assertEqual(len(wire), 1400)
        self.assertEqual(content_digest(wire).hex(), "430089f08bc0dc668b64a374c2a274a2a2f9b9216618b7e8baf5ed4e8d989cc7")
        self.assertEqual(content_digest(encode(value.uses[0].dependencies.objects[0], SCHEMA)).hex(),
                         "4bce60a245f95d2b11b604393e52c54832e04b659994ec2728086ddcfb4f220a")
        selection = SourceProofSelection(proof_fingerprint=content_digest(wire).hex(), dependency_indices=(0,))
        self.assertEqual(len(encode(selection, SCHEMA)), 204)
        self.assertEqual(decode(wire, SourceDurableProof, SCHEMA), value)

    def test_transitive_roster_roundtrip_and_field_order(self):
        value = vector1()
        ref = value.uses[0].dependencies.objects[0]
        revision = ref.revision
        collection = SourceCollectionId(kind=Category.COLLECTION, world_uid="world-test", descriptor=RegistryKey("members"))
        collection_ref = SourceCollectionVersionRef(collection_id=collection, revision=revision)
        body = ArtifactRef(kind=ArtifactKind.BLOB, format_key=RegistryKey("source.capture"), format_version=1,
                           content_hash="2" * 64, nbytes=100, row_count=None)
        object_body = SourceBodyVersion(source=ref, body=body)
        collection_body = SourceCollectionVersion(source=collection_ref, body=body)
        capture = SourceCapture(world_uid="world-test", objects=(object_body,), collections=(collection_body,))
        cases = (
            (20003, ArtifactKind.SQL_ROWS, ()),
            (20107, body, ("kind", "format_key", "format_version", "content_hash", "nbytes", "row_count")),
            (71001, Category.REGISTRY_MEMBER, ()),
            (71110, ref.object_id, ("kind", "world_uid", "descriptor", "member_key")),
            (71111, LibraryMemberId(kind=Category.LIBRARY_MEMBER, descriptor=RegistryKey("library"),
                                   template_uid="12345678-1234-1234-1234-123456789abc"), ("kind", "descriptor", "template_uid")),
            (71112, EntityObjectId(kind=Category.ENTITY, world_uid="world-test", descriptor=RegistryKey("entity"),
                                  entity_uid="entity"), ("kind", "world_uid", "descriptor", "entity_uid")),
            (71113, SourceSettingsId(kind=Category.SETTINGS, world_uid="world-test", descriptor=RegistryKey("settings")),
             ("kind", "world_uid", "descriptor")),
            (71114, collection, ("kind", "world_uid", "descriptor")),
            (71120, revision, ("seq", "content_hash")),
            (71121, ref, ("object_id", "revision")),
            (71122, collection_ref, ("collection_id", "revision")),
            (71123, value.uses[0].dependencies, ("objects", "collections")),
            (71124, object_body, ("source", "body")),
            (71125, collection_body, ("source", "body")),
            (71126, SourceCollectionBody(collection=collection, members=(ref.object_id,)), ("collection", "members")),
            (71127, capture, ("world_uid", "objects", "collections")),
            (71128, SourceCaptureWitness(capture_uid="capture", world_uid="world-test", capture_body=body),
             ("capture_uid", "world_uid", "capture_body")),
            (71129, value.uses[0].capture, ("world_uid", "artifact")),
            (71130, value.uses[0], ("capture", "dependencies")),
            (71131, value, ("schema_version", "world_uid", "uses")),
            (71138, SourceProofSelection(proof_fingerprint="3" * 64, dependency_indices=(0,)),
             ("proof_fingerprint", "dependency_indices")),
        )
        self.assertEqual({entry.type_id for entry in SCHEMA.entries}, {identity for identity, _, _ in cases})
        for identity, item, names in cases:
            with self.subTest(identity=identity):
                entry = next(entry for entry in SCHEMA.entries if entry.type_id == identity)
                self.assertIs(entry.python_type, type(item))
                self.assertEqual(entry.kind, CanonicalTypeKind.RECORD if names else CanonicalTypeKind.ENUM)
                if names:
                    self.assertEqual(tuple(type(item).model_fields), names)
                self.assertEqual(decode(encode(item, SCHEMA), type(item), SCHEMA), item)
        restored = decode(encode(value, SCHEMA), SourceDurableProof, SCHEMA)
        self.assertIs(type(restored.uses[0].dependencies.objects[0].object_id.member_key), SourceMemberKey)
        self.assertIs(type(restored.uses[0].dependencies.objects[0].object_id.descriptor), RegistryKey)

    def test_shared_composition_and_collision_refusals(self):
        merged = merge_manifests(ARTIFACT_CORE_SCHEMA, SNAPSHOT_CORE_SCHEMA, PACK_PIN_SCHEMA, SCHEMA)
        self.assertEqual(encode(vector1(), merged), encode(vector1(), SCHEMA))
        for entry in SCHEMA.entries:
            if entry.type_id in (20003, 20107):
                self.assertIn(entry, ARTIFACT_CORE_SCHEMA.entries)
        for identity, owner, kind in ((71131, SourceProofReadInput, CanonicalTypeKind.RECORD),
                                      (79999, SourceDurableProof, CanonicalTypeKind.RECORD),
                                      (71131, SourceDurableProof, CanonicalTypeKind.ENUM)):
            other = CanonicalSchemaManifest(entries=(RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind),))
            with self.subTest(identity=identity, owner=owner), self.assertRaises(CanonicalEncodingError):
                merge_manifests(SCHEMA, other)
        with self.assertRaises(ValidationError):
            SCHEMA.entries = ()

    def test_requests_results_errors_are_not_registered(self):
        proof = vector1()
        failure = SourceFailure(operation=SourceOperation.READ, field_issues=(), logic_issues=(SourceLogicIssue(
            code=SourceLogicCode.WRONG_WORLD, group_index=None, use_index=None, source=None, artifact=None),))
        for value in (SourceProofReadInput(world_uid="world-test", proof=proof),
                      SourceProofResult(proof=proof, durable_refs=(proof.uses[0].capture.artifact,)), failure):
            with self.subTest(owner=type(value).__name__), self.assertRaises(CanonicalEncodingError):
                encode(value, SCHEMA)

    def test_malformed_wire_wrong_root_and_version(self):
        wire = bytes.fromhex(V0_HEX)
        for bad in (wire[:-1], wire + b"x", wire.replace(bytes.fromhex("000115db"), bytes.fromhex("000115dc"), 1),
                    wire.replace(bytes.fromhex("0200000000000000020001"), bytes.fromhex("0200000000000000020002"), 1)):
            with self.subTest(bad=bad), self.assertRaises(CanonicalEncodingError):
                decode(bad, SourceDurableProof, SCHEMA)
        with self.assertRaises(CanonicalEncodingError):
            decode(wire, SourceProofSelection, SCHEMA)
        for version in (True, 2):
            forged = SourceDurableProof.model_construct(schema_version=version, world_uid="world-test", uses=())
            with self.assertRaises(CanonicalEncodingError):
                encode(forged, SCHEMA)

    def test_history_and_manifest_extension_preserve_v1(self):
        first = vector1()
        ref = first.uses[0].dependencies.objects[0]
        capture = first.uses[0].capture.model_copy(update={"artifact": first.uses[0].capture.artifact.model_copy(
            update={"content_hash": "2" * 64})})
        new_ref = SourceVersionRef(object_id=ref.object_id, revision=SourceRevision(seq=2, content_hash="3" * 64))
        second_use = SourceCaptureUsage(capture=capture, dependencies=SourceDependencySet(objects=(new_ref,), collections=()))
        proof = SourceDurableProof(schema_version=1, world_uid="world-test", uses=(first.uses[0], second_use))
        wire = encode(proof, SCHEMA)
        self.assertEqual(decode(wire, SourceDurableProof, SCHEMA), proof)
        reversed_schema = CanonicalSchemaManifest(entries=tuple(reversed(SCHEMA.entries)))
        self.assertEqual(encode(proof, reversed_schema), wire)
        extended = merge_manifests(SCHEMA, CanonicalSchemaManifest(entries=(RegisteredTypeEntry(
            type_id=79999, python_type=SourceProofReadInput, kind=CanonicalTypeKind.RECORD),)))
        self.assertEqual(encode(first, extended), encode(first, SCHEMA))
        self.assertEqual(decode(encode(first, SCHEMA), SourceDurableProof, extended), first)
        changed = SourceDurableProof(schema_version=1, world_uid="world-test", uses=(SourceCaptureUsage(
            capture=capture, dependencies=first.uses[0].dependencies),))
        self.assertNotEqual(content_digest(encode(changed, SCHEMA)), content_digest(encode(first, SCHEMA)))

    def test_cold_process_roundtrip(self):
        wire = encode(vector1(), SCHEMA)
        script = """
import sys
from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1 as S
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.encoding.canonicalCodec import decode, encode
sys.stdout.buffer.write(encode(decode(sys.stdin.buffer.read(), SourceDurableProof, S), S))
"""
        result = subprocess.run([sys.executable, "-B", "-c", script], input=wire, capture_output=True, check=True)
        self.assertEqual(result.stdout, wire)


if __name__ == "__main__":
    unittest.main()
