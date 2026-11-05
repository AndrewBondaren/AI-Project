"""Structural refusal must precede even the first nested domain constructor."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.boundedCanonicalDecode import decode_bounded, validate_bounded
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.hydrology.pack.root import HydrologyPackRoot, HydrologyShardRef
from app.dataModel.hydrology.pack.shard import HydrologyPackShard
from app.dataModel.encoding.decodeLimits import CollectionLimit, DecodeLimits, RecordLimits
from app.application.encoding.canonicalCodec import CanonicalEncodingError, encode
from app.application.worldData.generators.hydrology.encoding.packSchema import OPEN_WATER_PACK_SCHEMA_V1 as MANIFEST
from app.dataModel.planning.identity.planRef import PlanRef
from tests.spatial_pack.test_storage_schema import records


def tlv(tag, body):
    return bytes([tag]) + len(body).to_bytes(8, "big") + body


class StructuralLimitsTests(TestCase):
    limits = DecodeLimits(max_bytes=16 * 1024**2, max_nodes=524288, max_depth=64, max_items=65536)

    def test_exact_nodes_width_and_byte_limits(self):
        data = encode((1, 1, 2), MANIFEST)
        limits = DecodeLimits(max_bytes=len(data), max_nodes=4, max_depth=2, max_items=3)
        validate_bounded(data, tuple[int, ...], MANIFEST, limits=limits)
        for bad in (replace(limits, max_bytes=len(data)-1), replace(limits, max_items=2),
                    replace(limits, max_nodes=3)):
            with self.subTest(bad=bad), self.assertRaises(CanonicalEncodingError):
                validate_bounded(data, tuple[int, ...], MANIFEST, limits=bad)

    def test_field_binding_rejects_missing_scalar_and_wrong_owner(self):
        for selector, error in ((lambda shard: shard.missing, "no such field"),
                                (lambda shard: shard.tx, "expected canonical collection")):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                RecordLimits(HydrologyPackShard, (
                    CollectionLimit(tuple[int, ...], ref=FieldRef(lambda: HydrologyPackShard, selector), maximum=1),
                ))
        cap = CollectionLimit(tuple[HydrologyShardRef, ...], ref=FieldRef(lambda: HydrologyPackRoot, lambda root: root.shards), maximum=1)
        with self.assertRaisesRegex(ValueError, "bounded field belongs to"):
            RecordLimits(HydrologyPackShard, (cap,))

    def test_field_contract_rejects_wrong_container_and_nested_item(self):
        for expected in (frozenset[HydrologyShardRef], tuple[PlanRef, ...], tuple[HydrologyShardRef]):
            with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, "collection type mismatch"):
                CollectionLimit(expected, ref=FieldRef(lambda: HydrologyPackRoot, lambda root: root.shards), maximum=1)

    def test_depth_counts_top_as_one(self):
        data, annotation = encode(True, MANIFEST), bool
        for _ in range(63):
            data, annotation = tlv(8, data), tuple[annotation]
        validate_bounded(data, annotation, MANIFEST, limits=self.limits)
        with self.assertRaisesRegex(CanonicalEncodingError, "depth/node"):
            validate_bounded(tlv(8, data), tuple[annotation], MANIFEST, limits=self.limits)

    def test_hard_width_limit(self):
        data = tlv(8, tlv(0, b"") * 65537)
        with self.assertRaisesRegex(CanonicalEncodingError, "collection limit"):
            validate_bounded(data, tuple[type(None), ...], MANIFEST, limits=self.limits)

    def test_root_and_shard_hard_node_boundaries(self):
        # One outer tuple and N inner tuples. Count the wrapper for each tuple.
        null = tlv(0, b"")
        for budget, groups in ((262144, 4), (524288, 8)):
            sizes = [65535] * groups
            sizes[-1] -= 1
            limits = replace(self.limits, max_nodes=budget)
            for extra in (0, 1):
                sizes[-1] += extra
                data = tlv(8, b"".join(tlv(8, null*n) for n in sizes))
                annotation = tuple[tuple[type(None), ...], ...]
                if extra:
                    with self.assertRaisesRegex(CanonicalEncodingError, "depth/node limit"):
                        validate_bounded(data, annotation, MANIFEST, limits=limits)
                else:
                    validate_bounded(data, annotation, MANIFEST, limits=limits)

    def test_noncanonical_scalars_and_sets(self):
        one, two = encode(1, MANIFEST), encode(2, MANIFEST)
        for data, expected in ((tlv(9, two+one), frozenset[int]), (tlv(9, one+one), frozenset[int]),
                               (tlv(2, b"\x01\x00"), int), (tlv(2, b"\x00\x00\x01"), int),
                               (tlv(1, b"\x02"), bool), (tlv(3, bytes.fromhex("8000000000000000")), float),
                               (tlv(4, b"\xff"), str), (tlv(10, b""), bytes)):
            with self.subTest(data=data), self.assertRaises(CanonicalEncodingError):
                validate_bounded(data, expected, MANIFEST, limits=self.limits)

    def test_late_corruption_before_nested_construction(self):
        root, _ = records()
        data = encode(root, MANIFEST)
        # Last descriptor follows an otherwise valid source PlanRef.
        hash_field = encode("content_hash", MANIFEST)
        altered = data.replace(hash_field, encode("content_hosh", MANIFEST))
        self.assertNotEqual(data, altered)
        type_id = encode(60002, MANIFEST)
        unknown = data.replace(type_id, encode(60099, MANIFEST))
        self.assertNotEqual(data, unknown)
        for bad in (data[:-1], data+b"x", altered, unknown, b"\x07"+b"\xff"*8,
                    data.replace(encode("row_count", MANIFEST), encode("row_counx", MANIFEST))):
            with self.subTest(size=len(bad)), patch.object(PlanRef, "model_validate", side_effect=AssertionError), \
                    self.assertRaises(CanonicalEncodingError):
                decode_bounded(bad, type(root), MANIFEST, limits=self.limits)

    def test_schema_field_cap_and_scalar_type_refuse_before_models(self):
        root, _ = records()
        data = encode(root, MANIFEST)
        cap = CollectionLimit(tuple[HydrologyShardRef, ...], ref=FieldRef(lambda: HydrologyPackRoot, lambda root: root.shards), maximum=0)
        limits = replace(self.limits, field_sizes=(RecordLimits(type(root), (cap,)),))
        # Bytes instead of int in a late token, preserving its encoded length.
        old = encode(root.shards[0].artifact.nbytes, MANIFEST)
        index = data.rindex(old)
        wrong_type = data[:index] + bytes([5]) + data[index+1:]
        with patch.object(PlanRef, "model_validate", side_effect=AssertionError):
            with self.assertRaisesRegex(CanonicalEncodingError, "collection limit"):
                decode_bounded(data, type(root), MANIFEST, limits=limits)
            with self.assertRaisesRegex(CanonicalEncodingError, "field type"):
                decode_bounded(wrong_type, type(root), MANIFEST, limits=self.limits)
