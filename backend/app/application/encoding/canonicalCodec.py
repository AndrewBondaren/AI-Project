"""Compatibility API; the single canonical implementation lives in app.encoding."""

from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.encoding.canonicalCodec import (
    CanonicalCodec, CanonicalEncodingError, content_digest, decode, encode, merge_manifests,
    _decode_one, _decode_scalar, _tuple,
)


def digest(value: object, manifest: CanonicalSchemaManifest) -> bytes:
    """Keep the historical composition/patch boundary without duplicating encoding."""
    return content_digest(encode(value, manifest))
