"""Canonical open-water V1 root and shard codecs for in-memory artifacts."""
from app.application.encoding.boundedCanonicalDecode import decode_bounded, validate_bounded
from app.encoding.canonicalCodec import CanonicalEncodingError, encode
from app.application.worldData.generators.hydrology.encoding import packSchema
from app.application.worldData.generators.hydrology.encoding.packFormats import require_v1
from app.dataModel.hydrology.pack.root import HydrologyPackRoot
from app.dataModel.hydrology.pack.shard import BED_LIMITS, COVERAGE_LIMITS, HydrologyPackShard
from app.dataModel.hydrology.pack.profile import ROOT_V1, SHARD_V1
from app.dataModel.encoding.decodeLimits import RecordLimits
from app.dataModel.patch.values import FormatVersion


_ROOT = ROOT_V1.decode_limits(RecordLimits(HydrologyPackRoot, HydrologyPackRoot.collection_limits))
_SHARD = SHARD_V1.decode_limits(COVERAGE_LIMITS, BED_LIMITS,
                                RecordLimits(HydrologyPackShard, HydrologyPackShard.collection_limits))


def _encode(record, expected, limits):
    if type(record) is not expected:
        raise CanonicalEncodingError("unexpected open-water top-level type")
    packSchema.require_pack_record_v1(record)
    manifest = packSchema.OPEN_WATER_PACK_SCHEMA_V1
    payload = encode(record, manifest)
    validate_bounded(payload, expected, manifest, limits=limits)
    return payload


def _decode(payload, version, expected, limits):
    require_v1(version)
    packSchema.require_pack_schema_v1()
    record = decode_bounded(payload, expected, packSchema.OPEN_WATER_PACK_SCHEMA_V1, limits=limits)
    packSchema.require_pack_record_v1(record)
    return record


def encode_root(root: HydrologyPackRoot) -> bytes:
    return _encode(root, HydrologyPackRoot, _ROOT)


def encode_shard(shard: HydrologyPackShard) -> bytes:
    return _encode(shard, HydrologyPackShard, _SHARD)


def decode_root(payload: bytes, version: FormatVersion) -> HydrologyPackRoot:
    return _decode(payload, version, HydrologyPackRoot, _ROOT)


def decode_shard(payload: bytes, version: FormatVersion) -> HydrologyPackShard:
    return _decode(payload, version, HydrologyPackShard, _SHARD)
