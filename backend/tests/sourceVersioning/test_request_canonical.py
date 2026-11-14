"""Request wire identity is independent of proof fingerprints and authority."""

import unittest

from app.application.artifacts.encoding.coreManifest import ARTIFACT_CORE_SCHEMA
from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.application.worldData.sourceVersioning.encoding.sourceProofRequestSchemaV1 import (
    SOURCE_PROOF_REQUEST_ENCODING_V1 as SCHEMA, SOURCE_PROOF_REQUEST_SCHEMA_V1 as FRAGMENT,
)
from app.application.worldData.sourceVersioning.encoding.sourceProofSchemaV1 import SOURCE_PROOF_SCHEMA_V1
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.sourceVersioning.sourceCaptureUsage import SourceCaptureUsage
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofReadInput
from app.dataModel.sourceVersioning.sourceVersionRef import SourceVersionRef
from app.dataModel.worldPack.encoding.pinBindings import PACK_PIN_SCHEMA
from app.encoding.canonicalCodec import CanonicalEncodingError, content_digest, decode, encode, merge_manifests
from tests.sourceVersioning.test_canonical import V0_HEX, vector1


# Hand-assembled TLV layout plus the accepted literal proof V0, not encoder output.
REQUEST_V0_HEX = (
    "0700000000000001040800000000000000fb02000000000000000400011621"
    "0800000000000000e5080000000000000025040000000000000009776f726c645f756964"
    "04000000000000000a776f726c642d746573740800000000000000ae04000000000000000570726f6f66"
    + V0_HEX
)


def request(proof: SourceDurableProof) -> SourceProofReadInput:
    return SourceProofReadInput(world_uid=proof.world_uid, proof=proof)


class SourceRequestCanonicalTests(unittest.TestCase):
    def test_exact_registration_and_literal_golden(self):
        self.assertEqual(len(FRAGMENT.entries), 1)
        entry = FRAGMENT.entries[0]
        self.assertEqual(entry.type_id, 71201)
        self.assertIs(entry.python_type, SourceProofReadInput)
        self.assertIs(entry.kind, CanonicalTypeKind.RECORD)
        self.assertEqual(tuple(SourceProofReadInput.model_fields), ("world_uid", "proof"))
        self.assertEqual(SCHEMA.entries, SOURCE_PROOF_SCHEMA_V1.entries + FRAGMENT.entries)
        value = request(SourceDurableProof(schema_version=1, world_uid="world-test", uses=()))
        wire = encode(value, SCHEMA)
        self.assertEqual(wire.hex(), REQUEST_V0_HEX)
        self.assertEqual(len(wire), 269)
        self.assertEqual(content_digest(wire).hex(), "7c1637a9909f400dbfa18c6d364ae232ac277705a56854997e17fdf7615dcfec")
        restored = decode(bytes.fromhex(REQUEST_V0_HEX), SourceProofReadInput, SCHEMA)
        self.assertIs(type(restored), SourceProofReadInput)
        self.assertEqual(restored, value)
        self.assertEqual(encode(restored, SCHEMA), wire)

    def test_empty_nonempty_history_and_proof_invariance(self):
        first = vector1()
        ref = first.uses[0].dependencies.objects[0]
        capture = first.uses[0].capture.model_copy(update={"artifact": first.uses[0].capture.artifact.model_copy(
            update={"content_hash": "2" * 64})})
        revision = SourceVersionRef(object_id=ref.object_id, revision=SourceRevision(seq=2, content_hash="3" * 64))
        use = SourceCaptureUsage(capture=capture, dependencies=SourceDependencySet(objects=(revision,), collections=()))
        history = SourceDurableProof(schema_version=1, world_uid="world-test", uses=first.uses + (use,))
        empty = SourceDurableProof(schema_version=1, world_uid="world-test", uses=())
        merged = merge_manifests(ARTIFACT_CORE_SCHEMA, SNAPSHOT_CORE_SCHEMA, PACK_PIN_SCHEMA, SCHEMA)
        for proof in (empty, first, history):
            with self.subTest(uses=len(proof.uses)):
                value = request(proof)
                wire = encode(value, SCHEMA)
                self.assertEqual(decode(wire, SourceProofReadInput, SCHEMA), value)
                self.assertEqual(encode(value, merged), wire)
                self.assertEqual(encode(value, CanonicalSchemaManifest(entries=tuple(reversed(SCHEMA.entries)))), wire)
                self.assertEqual(encode(proof, SCHEMA), encode(proof, SOURCE_PROOF_SCHEMA_V1))
                self.assertEqual(decode(wire, SourceProofReadInput, merged).proof, proof)
                self.assertNotEqual(wire, encode(proof, SCHEMA))
        self.assertEqual(encode(empty, SCHEMA).hex(), V0_HEX)
        self.assertEqual(content_digest(encode(first, SCHEMA)).hex(),
                         "430089f08bc0dc668b64a374c2a274a2a2f9b9216618b7e8baf5ed4e8d989cc7")

    def test_proof_manifest_and_fragment_are_not_request_codecs(self):
        value = request(vector1())
        for manifest in (SOURCE_PROOF_SCHEMA_V1, FRAGMENT):
            with self.subTest(manifest=manifest), self.assertRaises(CanonicalEncodingError):
                encode(value, manifest)
            with self.assertRaises(CanonicalEncodingError):
                decode(encode(value, SCHEMA), SourceProofReadInput, manifest)

    def test_malformed_wire_and_wrong_root(self):
        wire = bytes.fromhex(REQUEST_V0_HEX)
        for bad in (wire[:-1], wire + b"x",
                    wire.replace(bytes.fromhex("00011621"), bytes.fromhex("00011622"), 1),
                    wire.replace(b"proof", b"other", 1),
                    wire.replace(bytes.fromhex("0200000000000000020001"),
                                 bytes.fromhex("0200000000000000020002"), 1)):
            with self.subTest(bad=bad), self.assertRaises(CanonicalEncodingError):
                decode(bad, SourceProofReadInput, SCHEMA)
        with self.assertRaises(CanonicalEncodingError):
            decode(wire, SourceDurableProof, SCHEMA)
        with self.assertRaises(CanonicalEncodingError):
            decode(bytes.fromhex(V0_HEX), SourceProofReadInput, SCHEMA)
        # Reorder the two complete field TLVs without altering enclosing lengths.
        fields_start = 40
        first_field_end = 86
        reordered = wire[:fields_start] + wire[first_field_end:] + wire[fields_start:first_field_end]
        with self.assertRaises(CanonicalEncodingError):
            decode(reordered, SourceProofReadInput, SCHEMA)

    def test_forged_input_is_not_normalized(self):
        proof = vector1()
        for value in (
            SourceProofReadInput.model_construct(world_uid="foreign", proof=proof),
            SourceProofReadInput.model_construct(world_uid="world-test"),
            SourceProofReadInput.model_construct(world_uid="world-test", proof=SourceDurableProof.model_construct(
                schema_version=True, world_uid="world-test", uses=())),
        ):
            with self.subTest(value=value), self.assertRaises(CanonicalEncodingError):
                encode(value, SCHEMA)

    def test_merge_rejects_id_owner_and_kind_collisions(self):
        self.assertEqual(merge_manifests(SCHEMA, FRAGMENT), SCHEMA)
        for identity, owner, kind in ((71201, SourceDurableProof, CanonicalTypeKind.RECORD),
                                      (79998, SourceProofReadInput, CanonicalTypeKind.RECORD),
                                      (71201, SourceProofReadInput, CanonicalTypeKind.ENUM)):
            other = CanonicalSchemaManifest(entries=(RegisteredTypeEntry(
                type_id=identity, python_type=owner, kind=kind),))
            with self.subTest(identity=identity, owner=owner), self.assertRaises(CanonicalEncodingError):
                merge_manifests(SCHEMA, other)


if __name__ == "__main__":
    unittest.main()
