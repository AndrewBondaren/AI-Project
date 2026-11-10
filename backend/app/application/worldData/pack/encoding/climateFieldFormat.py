"""Pack-owned artifact format for existing coarse and fine climate field bytes."""

from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.worldData.pack.io.packBlobWire import parse_climate_field_payload
from app.application.worldData.pack.io.tileCodec import PAYLOAD_KIND_CLIMATE, TileCodec
from app.dataModel.artifacts.references import ArtifactKind
from app.dataModel.worldPack.wire.climateFieldWire import CLIMATE_FIELD_FORMAT_KEY, CLIMATE_FIELD_FORMAT_VERSION, ClimateFieldWire


def decode_climate_field(payload: bytes) -> ClimateFieldWire:
    if type(payload) is not bytes:
        raise TypeError("climate artifact requires bytes")
    codec = TileCodec(codec_version=CLIMATE_FIELD_FORMAT_VERSION)
    if not payload.startswith(codec.pack_header(PAYLOAD_KIND_CLIMATE)):
        raise ValueError("expected climate field BLOB header")
    _, field = codec.decode(payload)
    return parse_climate_field_payload(field)


def _validated_bytes(payload: bytes) -> bytes:
    decode_climate_field(payload)
    return payload


def _decode(payload: bytes, version: int) -> bytes:
    if type(version) is not int or version != CLIMATE_FIELD_FORMAT_VERSION:
        raise ValueError("unsupported climate field artifact version")
    return _validated_bytes(payload)


CLIMATE_FIELD_FORMAT = ArtifactFormatContract(
    key=CLIMATE_FIELD_FORMAT_KEY, kind=ArtifactKind.BLOB,
    supported_versions=frozenset({CLIMATE_FIELD_FORMAT_VERSION}), content_model=bytes,
    encode=_validated_bytes, decode=_decode,
)
