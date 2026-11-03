"""Pure bytes contracts for open-water artifacts."""
from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.encoding.canonicalCodec import CanonicalEncodingError
from app.dataModel.artifacts.references import ArtifactKind, FormatVersion
from app.dataModel.hydrology.pack.profile import FORMAT_VERSION, ROOT_V1, SHARD_V1, OpenWaterArtifactV1


class UnsupportedPackFormat(CanonicalEncodingError):
    """The caller requested an unsupported open-water artifact format version."""


def require_v1(version: FormatVersion) -> None:
    if type(version) is not int or version != FORMAT_VERSION:
        raise UnsupportedPackFormat("unsupported open-water artifact version")


def _bytes(payload: bytes) -> bytes:
    if type(payload) is not bytes:
        raise CanonicalEncodingError("expected immutable artifact bytes")
    return payload


def _decode(payload: bytes, version: FormatVersion) -> bytes:
    require_v1(version)
    return _bytes(payload)


def _contract(profile: OpenWaterArtifactV1) -> ArtifactFormatContract[bytes]:
    return ArtifactFormatContract(key=profile.key, kind=ArtifactKind.BLOB, supported_versions=frozenset({FORMAT_VERSION}),
                                  content_model=bytes, encode=_bytes, decode=_decode)


ROOT_FORMAT = _contract(ROOT_V1)
SHARD_FORMAT = _contract(SHARD_V1)
