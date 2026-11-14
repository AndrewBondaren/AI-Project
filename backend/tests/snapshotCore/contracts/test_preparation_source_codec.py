import unittest
from uuid import UUID

from app.application.publication.encoding.preparationSourceBindingCodec import PreparationSourceBindingCodec
from app.application.publication.encoding.preparationSourceManifest import (
    PREPARATION_SOURCE_ENCODING as SCHEMA, PREPARATION_SOURCE_SCHEMA,
)
from app.application.worldData.sourceVersioning.encoding.sourceProofRequestSchemaV1 import SOURCE_PROOF_REQUEST_ENCODING_V1
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, PinHolder, VerifiedArtifactRef
from app.dataModel.publication.preparationSourceAuthority import PreparationSourceBinding
from app.dataModel.publication.preparationSourceBindingIssue import PreparationSourceBindingFieldCode as Code
from app.encoding.canonicalCodec import CanonicalEncodingError, encode
from tests.snapshotCore.contracts.test_preparation_source_binding import binding
from tests.sourceVersioning.test_request_canonical import REQUEST_V0_HEX


def golden_binding():
    # Independent fixed TLV fixture: no production encoder or model reflection.
    def tlv(tag, body):
        return bytes((tag,)) + len(body).to_bytes(8, "big") + body
    def string(value):
        return tlv(4, value.encode("utf-8"))
    def integer(value):
        return tlv(2, b"\x00" + value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big"))
    def sequence(*items):
        return tlv(8, b"".join(items))
    def record(identity, *pairs):
        return tlv(7, sequence(integer(identity), sequence(*(
            sequence(string(key), value) for key, value in pairs))))
    def enum(identity, value):
        return tlv(6, sequence(integer(identity), string(value)))
    target = record(20108, ("operation_id", string("op")), ("world_uid", string("world-test")),
                    ("kind", enum(20004, "pack_activation")),
                    ("preparation_fingerprint", string("1" * 64)), ("fence", integer(1)))
    pin = record(20205, ("store_id", tlv(10, bytes(15) + b"\x01")),
                 ("execution_id", string("exec")), ("invocation_id", string("inv")),
                 ("logical_read_key", string("base")), ("pin_id", string("pin")),
                 ("world_uid", string("world-test")), ("max_bytes", integer(1024)))
    manifest = record(20107, ("kind", enum(20003, "sql_rows")),
                      ("format_key", string("source.capture-witness")), ("format_version", integer(1)),
                      ("content_hash", string("0" * 64)), ("nbytes", integer(100)), ("row_count", integer(1)))
    origin = record(20309, ("kind", enum(20308, "pinned_manifest")), ("pin", pin), ("manifest", manifest))
    return record(20310, ("target", target), ("request", bytes.fromhex(REQUEST_V0_HEX)),
                  ("origin", origin), ("sources", sequence()))


class PreparationSourceCodecTests(unittest.TestCase):
    def test_fixed_layout_vector(self):
        value = binding()
        value = value.model_copy(update={"request": value.request.model_copy(update={
            "proof": value.request.proof.model_copy(update={"uses": ()})})})
        codec = PreparationSourceBindingCodec()
        self.assertEqual(codec.encode(value), golden_binding())
        self.assertEqual(codec.decode(golden_binding()), value)

    def test_empty_and_full_roundtrip_and_request_projection(self):
        value = binding()
        codec = PreparationSourceBindingCodec()
        child = value.origin.manifest.model_copy(update={"content_hash": "2" * 64})
        full = value.model_copy(update={"sources": (
            VerifiedArtifactRef(ref=value.origin.manifest, holder=PinHolder(pin_id="pin")),
            VerifiedArtifactRef(ref=child, holder=ArtifactRetentionHolder(artifact=value.origin.manifest)),
        )})
        for original in (value, full):
            wire = codec.encode(original)
            restored = codec.decode(wire)
            self.assertEqual(restored, original)
            self.assertIs(type(restored.origin.pin.store_id), UUID)
            self.assertEqual(codec.encode(restored), wire)
            self.assertEqual(codec.encode_request(restored.request),
                             encode(original.request, SOURCE_PROOF_REQUEST_ENCODING_V1))
        self.assertEqual(tuple(e.type_id for e in PREPARATION_SOURCE_SCHEMA.entries), (20308, 20309, 20310))
        self.assertNotIn(20128, tuple(e.type_id for e in SCHEMA.entries))

    def test_relation_failure_preserves_typed_causes_both_directions(self):
        value = binding()
        child = value.origin.manifest.model_copy(update={"content_hash": "2" * 64})
        invalid = VerifiedArtifactRef(ref=child, holder=PinHolder(pin_id="pin"))
        value = value.model_copy(update={"sources": (invalid, invalid)})
        codec = PreparationSourceBindingCodec()
        for action in (lambda: codec.encode(value), lambda: codec.decode(encode(value, SCHEMA))):
            with self.assertRaises(CanonicalEncodingError) as caught:
                action()
            self.assertEqual(tuple(i.code for i in caught.exception.args[0]), (
                Code.INVALID_SOURCE_HOLDER, Code.DUPLICATE_SOURCE, Code.INVALID_SOURCE_HOLDER))

    def test_malformed_wrong_root_and_unknown_id(self):
        codec = PreparationSourceBindingCodec()
        value = binding()
        wire = codec.encode(value)
        for bad in (wire[:-1], wire + b"x", encode(value.request, SCHEMA),
                    wire.replace((20310).to_bytes(2, "big"), (20311).to_bytes(2, "big"), 1)):
            with self.subTest(payload=bad[:30]), self.assertRaises(CanonicalEncodingError):
                codec.decode(bad)

    def test_origin_change_changes_bytes_even_without_sources(self):
        value = binding()
        changed = value.model_copy(update={"origin": value.origin.model_copy(update={
            "pin": value.origin.pin.model_copy(update={"pin_id": "another"})})})
        codec = PreparationSourceBindingCodec()
        self.assertNotEqual(codec.encode(value), codec.encode(changed))
        self.assertEqual(codec.encode_request(value.request), codec.encode_request(changed.request))
