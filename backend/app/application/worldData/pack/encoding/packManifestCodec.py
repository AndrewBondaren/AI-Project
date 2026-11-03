"""Versioned World Pack JSON boundary. Disk publication belongs to the store."""
import json

from pydantic import BaseModel

from app.dataModel.worldPack.meta.spatial.domainRoot import SpatialDomainRootRef
from app.dataModel.worldPack.meta.worldPackManifest import (
    PACK_WIRE_VERSION, SPATIAL_PACK_WIRE_VERSION, WorldPackManifest, WorldPackManifestV2,
)
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume


def _unique_object(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError(f"duplicate manifest key: {key}")
        values[key] = value
    return values


def _invalid_constant(token: str):
    raise ValueError(f"invalid JSON constant: {token}")


def decode_manifest(payload: bytes) -> WorldPackManifest:
    raw = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    if not isinstance(raw, dict):
        raise ValueError("expected World Pack JSON object")
    version = raw.get("pack_version", PACK_WIRE_VERSION)
    if version == PACK_WIRE_VERSION:
        if "spatial_roots" in raw:
            raise ValueError("unexpected V1 spatial_roots")
        return WorldPackManifest.model_validate(raw)
    if version == SPATIAL_PACK_WIRE_VERSION:
        admitted = WorldPackManifestV2.model_validate_json(payload, strict=True, context=TerritoryVolume.STRICT_BOUNDS)
        return WorldPackManifest.model_validate(vars(admitted), strict=True)
    raise ValueError("unsupported World Pack version")


def require_legacy_manifest(manifest: WorldPackManifest, *, world_uid: str | None = None) -> None:
    if (type(manifest) is not WorldPackManifest or manifest.pack_version != PACK_WIRE_VERSION
            or type(manifest.spatial_roots) is not tuple or manifest.spatial_roots):
        raise ValueError("legacy World Pack writer requires V1 without spatial roots")
    if world_uid is not None and manifest.world_uid != world_uid:
        raise ValueError("foreign World Pack manifest")


def encode_legacy_manifest(manifest: WorldPackManifest) -> bytes:
    require_legacy_manifest(manifest)
    # Mutable legacy lists must still pass the original save-time validation.
    admitted = WorldPackManifest.model_validate(manifest.model_dump(mode="json"))
    return admitted.model_dump_json(indent=2).encode("utf-8")


def _require_pojo_tree(value: object) -> None:
    """Revalidate each actual record before its parent can trust that instance."""
    if isinstance(value, dict):
        raise ValueError("unexpected dictionary in typed V2 manifest")
    if isinstance(value, BaseModel):
        fields = vars(value)
        if fields.keys() != type(value).model_fields.keys():
            raise ValueError("incomplete or extra V2 record fields")
        for child in fields.values():
            _require_pojo_tree(child)
        admitted = type(value).model_validate(fields, strict=True, context=TerritoryVolume.STRICT_BOUNDS)
        if any(type(original) is not type(getattr(admitted, name)) or original != getattr(admitted, name)
               for name, original in fields.items()):
            raise ValueError("V2 record changed under strict admission")
    elif isinstance(value, (tuple, list)):
        for item in value:
            _require_pojo_tree(item)


def encode_candidate_manifest(manifest: WorldPackManifest) -> bytes:
    if type(manifest) is not WorldPackManifest or manifest.pack_version != SPATIAL_PACK_WIRE_VERSION:
        raise ValueError("candidate encoding requires V2")
    if type(manifest.spatial_roots) is not tuple or any(type(row) is not SpatialDomainRootRef for row in manifest.spatial_roots):
        raise ValueError("expected typed spatial root descriptors")
    _require_pojo_tree(manifest)
    return manifest.model_dump_json(indent=2, warnings="error").encode("utf-8")
