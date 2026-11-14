"""Canonical identity of the existing pin input; decoding grants no authority."""
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.worldPack.read.pinnedManifest import ManifestPinRead


PACK_PIN_SCHEMA = CanonicalSchemaManifest(entries=(
    RegisteredTypeEntry(type_id=20205, python_type=ManifestPinRead, kind=CanonicalTypeKind.RECORD),
))
