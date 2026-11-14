"""Native UUID wire contract shared by ordinary and budgeted readers."""
import unittest
from dataclasses import replace
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.application.encoding.boundedCanonicalDecode import decode_bounded, validate_bounded
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.encoding.canonicalCodec import CanonicalEncodingError, decode, encode


class UuidRecord(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    identity: UUID
    ordered: tuple[UUID, ...]
    unique: frozenset[UUID]


SCHEMA = CanonicalSchemaManifest(entries=(
    RegisteredTypeEntry(type_id=1, python_type=UuidRecord, kind=CanonicalTypeKind.RECORD),
))
LIMITS = DecodeLimits(max_bytes=4096, max_nodes=100, max_depth=20, max_items=10)
ONE_WIRE = bytes.fromhex("0a000000000000001000000000000000000000000000000001")


class UuidCodecTests(unittest.TestCase):
    def assert_round_trip(self, value, expected):
        wire = encode(value, SCHEMA)
        for result in (decode(wire, expected, SCHEMA),
                       decode_bounded(wire, expected, SCHEMA, limits=LIMITS)):
            self.assertIs(type(result), expected)
            self.assertEqual(result, value)
            self.assertEqual(encode(result, SCHEMA), wire)
        validate_bounded(wire, expected, SCHEMA, limits=LIMITS)

    def assert_rejected(self, wire, expected=UUID):
        for reader in (lambda: decode(wire, expected, SCHEMA),
                       lambda: decode_bounded(wire, expected, SCHEMA, limits=LIMITS),
                       lambda: validate_bounded(wire, expected, SCHEMA, limits=LIMITS)):
            with self.assertRaises(CanonicalEncodingError):
                reader()

    def test_native_vector_and_unrestricted_uuid_values(self):
        self.assertEqual(encode(UUID(int=1), SCHEMA), ONE_WIRE)
        for value in (UUID(int=0), UUID(int=1), UUID(int=(1 << 128) - 1),
                      UUID("00112233-4455-6677-8899-aabbccddeeff")):
            with self.subTest(value=value):
                self.assert_round_trip(value, UUID)
        self.assertEqual(encode(UUID("00112233-4455-6677-8899-aabbccddeeff"), SCHEMA),
                         bytes.fromhex("0a000000000000001000112233445566778899aabbccddeeff"))

    def test_nested_uuid_collections(self):
        values = (UUID(int=2), UUID(int=1))
        value = UuidRecord(identity=values[0], ordered=values, unique=frozenset(values))
        self.assert_round_trip(value, UuidRecord)
        restored = decode_bounded(encode(value, SCHEMA), UuidRecord, SCHEMA, limits=LIMITS)
        self.assertIs(type(restored.identity), UUID)
        self.assertTrue(all(type(item) is UUID for item in (*restored.ordered, *restored.unique)))

    def test_malformed_uuid_and_unknown_tags(self):
        for length in (0, 15, 17):
            with self.subTest(length=length):
                self.assert_rejected(b"\x0a" + length.to_bytes(8, "big") + bytes(length))
        for wire in (ONE_WIRE[:-1], ONE_WIRE + b"\x00", ONE_WIRE[:8],
                     b"\x0b" + ONE_WIRE[1:]):
            with self.subTest(wire=wire):
                self.assert_rejected(wire)

    def test_no_string_or_bytes_coercion(self):
        for expected in (str, bytes, int):
            with self.subTest(expected=expected):
                self.assert_rejected(ONE_WIRE, expected)
        for value in (str(UUID(int=1)), UUID(int=1).bytes, 1):
            with self.subTest(value=value):
                self.assert_rejected(encode(value, SCHEMA))

    def test_budget_checks_apply_to_uuid(self):
        nested = UuidRecord(identity=UUID(int=1), ordered=(UUID(int=1),), unique=frozenset())
        for value, expected, limits in (
            (UUID(int=1), UUID, replace(LIMITS, max_bytes=24)),
            (UUID(int=1), UUID, replace(LIMITS, max_nodes=0)),
            (UUID(int=1), UUID, replace(LIMITS, max_depth=0)),
            (nested, UuidRecord, replace(LIMITS, max_items=0)),
            (nested, UuidRecord, replace(LIMITS, max_depth=4)),
        ):
            with self.subTest(expected=expected, limits=limits):
                wire = encode(value, SCHEMA)
                for reader in (decode_bounded, validate_bounded):
                    with self.assertRaises(CanonicalEncodingError):
                        reader(wire, expected, SCHEMA, limits=limits)


if __name__ == "__main__":
    unittest.main()
