"""Storage registration for the exact JSON bytes of a World Pack V2 candidate."""
from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest
from app.dataModel.artifacts.references import ArtifactKind
from app.dataModel.worldPack.meta.manifestStorageFormat import (
    MANIFEST_FORMAT_KEY as MANIFEST_FORMAT_KEY, MANIFEST_STORAGE_VERSION as MANIFEST_STORAGE_VERSION,
)
from app.dataModel.worldPack.meta.worldPackManifest import SPATIAL_PACK_WIRE_VERSION


def manifest_format(max_bytes: int) -> ArtifactFormatContract[bytes]:
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("manifest storage requires a positive byte budget")

    def admit(payload: bytes) -> bytes:
        if type(payload) is not bytes or not 0 < len(payload) <= max_bytes:
            raise ValueError("manifest bytes outside storage budget")
        manifest = decode_manifest(payload)
        if manifest.pack_version != SPATIAL_PACK_WIRE_VERSION or manifest.content_hash is not None:
            raise ValueError("expected a World Pack V2 candidate manifest")
        return payload

    def decode(payload: bytes, version: int) -> bytes:
        if type(version) is not int or version != MANIFEST_STORAGE_VERSION:
            raise ValueError("unsupported manifest storage version")
        return admit(payload)

    return ArtifactFormatContract(key=MANIFEST_FORMAT_KEY, kind=ArtifactKind.BLOB,
                                  supported_versions=frozenset({MANIFEST_STORAGE_VERSION}),
                                  content_model=bytes, encode=admit, decode=decode)
