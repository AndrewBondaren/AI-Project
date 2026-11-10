"""Cache address of immutable manifest bytes; pin admission belongs to Pack."""
from app.application.artifacts.encoding.coreManifest import ARTIFACT_CORE_SCHEMA
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.cache.identity.cacheKey import CacheItemKey, CacheKey
from app.dataModel.worldPack.meta.manifestCacheContract import MANIFEST_BYTES_CONTRACT
from app.encoding.canonicalCodec import digest


def manifest_cache_key(ref: ArtifactRef) -> CacheKey[bytes]:
    checked = ArtifactRef.model_validate(ref, strict=True)
    if checked.kind is not ArtifactKind.BLOB:
        raise ValueError("manifest cache requires a BLOB descriptor")
    return CacheKey[bytes](contract=MANIFEST_BYTES_CONTRACT,
                           item_key=CacheItemKey(digest(checked, ARTIFACT_CORE_SCHEMA)))
