"""Binary tile blob codec — zstd + wire header."""

from __future__ import annotations

import hashlib
import struct

import orjson
import zstandard

from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults

PAYLOAD_KIND_WORLD_MAP = 0
PAYLOAD_KIND_FINE_TERRAIN = 1
PAYLOAD_KIND_CLIMATE = 2


def codec_version() -> int:
    return PackBakeDefaults.canonical_defaults().codec_version


CODEC_VERSION = codec_version()
_HEADER = struct.Struct("!BB")


class TileCodec:
    """Encode/decode pack blobs with versioned header."""

    def __init__(self, level: int | None = None, *, codec_version: int | None = None) -> None:
        defaults = PackBakeDefaults.canonical_defaults()
        self._codec_version = codec_version if codec_version is not None else defaults.codec_version
        self._compressor = zstandard.ZstdCompressor(level=level if level is not None else defaults.zstd_level)
        self._decompressor = zstandard.ZstdDecompressor()

    def encode(self, kind: int, payload: dict) -> bytes:
        body = orjson.dumps(payload)
        compressed = self._compressor.compress(body)
        return _HEADER.pack(self._codec_version, kind) + compressed

    def decode(self, data: bytes) -> tuple[int, dict]:
        if len(data) < _HEADER.size:
            raise ValueError("blob too short for header")
        version, kind = _HEADER.unpack_from(data)
        if version != self._codec_version:
            raise ValueError(f"unsupported codec version {version}")
        raw = self._decompressor.decompress(data[_HEADER.size :])
        payload = orjson.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        return kind, payload

    @staticmethod
    def content_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
