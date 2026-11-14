"""Pin input registration, independent wire vector and strict rejection."""
import unittest
from uuid import UUID

from app.application.artifacts.encoding.coreManifest import ARTIFACT_CORE_SCHEMA
from app.application.encoding.boundedCanonicalDecode import decode_bounded
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.worldPack.encoding.pinBindings import PACK_PIN_SCHEMA
from app.dataModel.worldPack.read.pinnedManifest import ManifestAddress, ManifestPinRead
from app.encoding.canonicalCodec import CanonicalEncodingError, content_digest, decode, encode, merge_manifests


LIMITS = DecodeLimits(max_bytes=4096, max_nodes=100, max_depth=20, max_items=20)
GOLDEN = bytes.fromhex(
    "07000000000000014a080000000000000141020000000000000003004eed08000000000000012c"
    "08000000000000002a04000000000000000873746f72655f69640a000000000000001000000000000000000000000000000001"
    "08000000000000002204000000000000000c657865637574696f6e5f696404000000000000000465786563"
    "08000000000000002204000000000000000d696e766f636174696f6e5f6964040000000000000003696e76"
    "0800000000000000260400000000000000106c6f676963616c5f726561645f6b657904000000000000000462617365"
    "08000000000000001b04000000000000000670696e5f696404000000000000000370696e"
    "080000000000000020040000000000000009776f726c645f756964040000000000000005776f726c64"
    "08000000000000001e0400000000000000096d61785f6279746573020000000000000003000400"
)


def pin_values():
    return dict(store_id=UUID(int=1), execution_id="exec", invocation_id="inv",
                logical_read_key="base", pin_id="pin", world_uid="world", max_bytes=1024)


def record_wire(pairs, identity=20205):
    payload = encode((identity, tuple(pairs)), PACK_PIN_SCHEMA)
    return b"\x07" + len(payload).to_bytes(8, "big") + payload


class PinCanonicalRegistrationTests(unittest.TestCase):
    def test_literal_golden_both_decoders_and_composition(self):
        pin = ManifestPinRead(**pin_values())
        self.assertEqual(len(GOLDEN), 339)
        self.assertEqual(content_digest(GOLDEN).hex(),
                         "aba1c78650c352504b3af0484341179769e2d82d091d495c2c09b273e96f0b32")
        self.assertEqual(encode(pin, PACK_PIN_SCHEMA), GOLDEN)
        merged = merge_manifests(ARTIFACT_CORE_SCHEMA, PACK_PIN_SCHEMA)
        self.assertEqual(encode(pin, merged), GOLDEN)
        for result in (decode(GOLDEN, ManifestPinRead, merged),
                       decode_bounded(GOLDEN, ManifestPinRead, merged, limits=LIMITS)):
            self.assertEqual(result, pin)
            self.assertIs(type(result.store_id), UUID)
            self.assertIs(type(result.execution_id), str)
            self.assertEqual(encode(result, merged), GOLDEN)

    def test_each_field_changes_wire(self):
        changes = dict(store_id=UUID(int=2), execution_id="other-exec", invocation_id="other-inv",
                       logical_read_key="other-key", pin_id="other-pin", world_uid="other-world", max_bytes=1025)
        for field, value in changes.items():
            with self.subTest(field=field):
                self.assertNotEqual(encode(ManifestPinRead(**(pin_values() | {field: value})), PACK_PIN_SCHEMA), GOLDEN)

    def test_malformed_wire_is_rejected(self):
        pairs = list(pin_values().items())
        wires = [record_wire(pairs[::-1]), record_wire(pairs[:-1]),
                 record_wire(pairs + [("extra", 1)]), record_wire(pairs, 20206),
                 GOLDEN[:-1], GOLDEN + b"\0"]
        for field, value in (("max_bytes", True), ("max_bytes", 0), ("execution_id", ""),
                             ("invocation_id", " leading"), ("pin_id", ""),
                             ("store_id", str(UUID(int=1)))):
            wires.append(record_wire((pin_values() | {field: value}).items()))
        for wire in wires:
            with self.subTest(wire=wire):
                for reader in (lambda: decode(wire, ManifestPinRead, PACK_PIN_SCHEMA),
                               lambda: decode_bounded(wire, ManifestPinRead, PACK_PIN_SCHEMA, limits=LIMITS)):
                    with self.assertRaises(CanonicalEncodingError):
                        reader()

    def test_manifest_conflicts_fail_and_exact_merge_is_idempotent(self):
        self.assertEqual(merge_manifests(PACK_PIN_SCHEMA, PACK_PIN_SCHEMA), PACK_PIN_SCHEMA)
        for identity, owner in ((20206, ManifestPinRead), (20205, ManifestAddress)):
            conflict = CanonicalSchemaManifest(entries=(RegisteredTypeEntry(
                type_id=identity, python_type=owner, kind=CanonicalTypeKind.RECORD),))
            with self.assertRaises(CanonicalEncodingError):
                merge_manifests(PACK_PIN_SCHEMA, conflict)


if __name__ == "__main__":
    unittest.main()
