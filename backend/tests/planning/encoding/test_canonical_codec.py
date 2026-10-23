"""PC-3E wire rejection, round trips, schema identities and fingerprint closure."""

from dataclasses import dataclass
from enum import StrEnum
from struct import pack
import unittest

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.application.encoding.canonicalCodec import CanonicalEncodingError, decode, digest, encode
from app.application.planning.service.planFingerprints import cache_item_key, input_fingerprint, output_fingerprint
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.planning.contracts.planContract import PlanContractMetadata
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.identity.planKey import PlanKey, PlanScopeKind, WorldPlanScope, RegionPlanScope
from app.dataModel.planning.identity.planRef import PlanRef


class Choice(StrEnum):
    ONE = "one"


class Record(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    choice: Choice
    pairs: tuple[tuple[str, int], ...]

    @model_validator(mode="after")
    def unique_map_keys(self):
        keys = tuple(key for key, value in self.pairs)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("duplicate or unordered map keys")
        return self


@dataclass(frozen=True)
class Plain:
    value: int
    labels: frozenset[str]


MANIFEST = CanonicalSchemaManifest(entries=tuple(RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind)
    for identity, owner, kind in ((1, Record, CanonicalTypeKind.RECORD), (2, Choice, CanonicalTypeKind.ENUM),
        (3, Plain, CanonicalTypeKind.RECORD), (4, PlanKey, CanonicalTypeKind.RECORD),
        (5, WorldPlanScope, CanonicalTypeKind.RECORD), (6, RegionPlanScope, CanonicalTypeKind.RECORD),
        (7, PlanScopeKind, CanonicalTypeKind.ENUM), (8, PlanRef, CanonicalTypeKind.RECORD),
        (9, PlanDependency, CanonicalTypeKind.RECORD))))


def tlv(tag, payload):
    return bytes([tag]) + len(payload).to_bytes(8, "big") + payload


class CanonicalCodecTests(unittest.TestCase):
    def test_round_trip_primitives_records_dataclasses_and_nested_sets(self):
        values = (None, False, True, -257, 256, 0, 1.5, "данные", b"data", Choice.ONE,
                  (None, b"x", frozenset((1, 2))), Plain(1, frozenset(("a", "b"))),
                  Record(choice=Choice.ONE, pairs=(("a", 1), ("b", 2))))
        for value in values:
            with self.subTest(value=value):
                encoded = encode(value, MANIFEST)
                self.assertEqual(decode(encoded, type(value), MANIFEST), value)
                self.assertEqual(encode(decode(encoded, type(value), MANIFEST), MANIFEST), encoded)

    def test_manifest_ids_are_positive_unique_and_kinds_are_closed(self):
        for invalid in (0, -1, True, "1"):
            with self.assertRaises(ValidationError):
                RegisteredTypeEntry(type_id=invalid, python_type=Record, kind=CanonicalTypeKind.RECORD)
        with self.assertRaises(ValidationError):
            CanonicalSchemaManifest(entries=(MANIFEST.entries[0], MANIFEST.entries[0]))
        wrong = CanonicalSchemaManifest(entries=(RegisteredTypeEntry(type_id=1, python_type=Record, kind=CanonicalTypeKind.ENUM),))
        with self.assertRaises(CanonicalEncodingError):
            encode(1, wrong)

    def test_reject_noncanonical_integer_float_boolean_and_unknown_tags(self):
        invalid = (tlv(2, b"\x01\x00"), tlv(2, b"\x00\x00\x01"), tlv(2, b"\x02\x01"),
                   tlv(3, pack(">d", -0.0)), tlv(3, pack(">d", float("nan"))),
                   tlv(3, pack(">d", float("inf"))), tlv(1, b"\x02"), tlv(0, b"x"),
                   tlv(99, b""), b"", encode(1, MANIFEST)[:-1], encode(1, MANIFEST) + b"x")
        for encoded in invalid:
            with self.subTest(encoded=encoded), self.assertRaises(CanonicalEncodingError):
                decode(encoded, object, MANIFEST)
        with self.assertRaises(CanonicalEncodingError):
            decode(encode(True, MANIFEST), int, MANIFEST)
        with self.assertRaises(CanonicalEncodingError):
            encode(Plain(True, frozenset()), MANIFEST)

    def test_unordered_encoding_is_sorted_and_duplicate_set_elements_rejected(self):
        first, second = sorted((encode("a", MANIFEST), encode("b", MANIFEST)))
        self.assertEqual(encode(frozenset(("b", "a")), MANIFEST), tlv(9, first + second))
        for body in (second + first, first + first):
            with self.assertRaises(CanonicalEncodingError):
                decode(tlv(9, body), frozenset, MANIFEST)
        self.assertNotEqual(encode(("a", "b"), MANIFEST), encode(("b", "a"), MANIFEST))

    def test_record_order_duplicate_missing_fields_unknown_ids_and_enum_members_rejected(self):
        for identity, pairs in ((999, ()), (1, (("pairs", ()), ("choice", Choice.ONE))),
                                (1, (("choice", Choice.ONE),)),
                                (1, (("choice", Choice.ONE), ("choice", Choice.ONE)))):
            encoded = tlv(7, encode((identity, pairs), MANIFEST))
            with self.assertRaises(CanonicalEncodingError):
                decode(encoded, Record, MANIFEST)
        with self.assertRaises(CanonicalEncodingError):
            decode(tlv(6, encode((2, "unknown"), MANIFEST)), Choice, MANIFEST)

    def test_duplicate_map_keys_rejected_using_the_existing_model_invariants(self):
        invalid = Record.model_construct(choice=Choice.ONE, pairs=(("a", 1), ("a", 2)))
        with self.assertRaises(CanonicalEncodingError):
            encode(invalid, MANIFEST)
        encoded = tlv(7, encode((1, (("choice", Choice.ONE), ("pairs", (("a", 1), ("a", 2))))), MANIFEST))
        with self.assertRaises(CanonicalEncodingError):
            decode(encoded, Record, MANIFEST)

    def test_all_three_fingerprints_are_distinct_and_cover_input_closure(self):
        metadata = PlanContractMetadata(id="phase", schema_version=1, algorithm_version=1)
        scope = WorldPlanScope()
        inputs = Plain(1, frozenset(("a", "b")))
        base = input_fingerprint(metadata, "world", scope, inputs, (), MANIFEST)
        key = PlanKey(world_uid="world", scope=scope, contract_id=metadata.id,
            schema_version=1, algorithm_version=1, input_fingerprint=base)
        output = output_fingerprint(inputs, (), (), MANIFEST)
        address = cache_item_key(key, MANIFEST)
        self.assertEqual({len(base), len(output), len(address)}, {32})
        self.assertEqual(len({base, output, address}), 3)
        for change in ({"id": "another"}, {"schema_version": 2}, {"algorithm_version": 2}):
            self.assertNotEqual(input_fingerprint(metadata.model_copy(update=change), "world", scope, inputs, (), MANIFEST), base)
        self.assertNotEqual(input_fingerprint(metadata, "another", scope, inputs, (), MANIFEST), base)
        self.assertNotEqual(input_fingerprint(metadata, "world", RegionPlanScope(region_uid="r"), inputs, (), MANIFEST), base)
        self.assertNotEqual(input_fingerprint(metadata, "world", scope, Plain(2, inputs.labels), (), MANIFEST), base)
        dependency = PlanDependency(slot="base", ref=PlanRef(key=key, output_fingerprint=output))
        self.assertNotEqual(input_fingerprint(metadata, "world", scope, inputs, (dependency,), MANIFEST), base)
        self.assertNotEqual(output_fingerprint(inputs, (dependency,), (), MANIFEST), output)
        self.assertNotEqual(cache_item_key(key.model_copy(update={"input_fingerprint": bytes(32)}), MANIFEST), address)
        self.assertEqual(digest(inputs, MANIFEST), digest(Plain(1, frozenset(("b", "a"))), MANIFEST))


if __name__ == "__main__":
    unittest.main()
