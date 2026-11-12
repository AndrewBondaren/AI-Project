"""Versioned World Pack JSON boundary. Disk publication belongs to the store."""
import json
from types import UnionType
from typing import get_args, get_origin

from pydantic import BaseModel
from pydantic_core import from_json

from app.dataModel.registryKey import RegistryKey
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
    # LEGACY REMOVE(SP-P-V1-REMOVE/V1-02) Remove historical missing-version/V1 dispatch after retirement.
    if version == PACK_WIRE_VERSION:
        if "spatial_roots" in raw:
            raise ValueError("unexpected V1 spatial_roots")
        return WorldPackManifest.model_validate(raw)
    if version == SPATIAL_PACK_WIRE_VERSION:
        admitted = WorldPackManifestV2.model_validate_json(
            payload, strict=True, extra="forbid", context=TerritoryVolume.STRICT_BOUNDS)
        return WorldPackManifest.model_validate(vars(admitted), strict=True)
    raise ValueError("unsupported World Pack version")


# LEGACY REMOVE(SP-P-V1-REMOVE/V1-02) Remove with the V1 store and writer callers.
def require_legacy_manifest(manifest: WorldPackManifest, *, world_uid: str | None = None) -> None:
    if (type(manifest) is not WorldPackManifest or manifest.pack_version != PACK_WIRE_VERSION
            or type(manifest.spatial_roots) is not tuple or manifest.spatial_roots):
        raise ValueError("legacy World Pack writer requires V1 without spatial roots")
    if world_uid is not None and manifest.world_uid != world_uid:
        raise ValueError("foreign World Pack manifest")
    manifest.validate_climate_addresses()


# LEGACY REMOVE(SP-P-V1-REMOVE/V1-02) Remove the V1 JSON encoder after writer cutover.
def encode_legacy_manifest(manifest: WorldPackManifest) -> bytes:
    require_legacy_manifest(manifest)
    # Mutable legacy lists must still pass the original save-time validation.
    admitted = WorldPackManifest.model_validate(manifest.model_dump(mode="json"))
    return admitted.model_dump_json(indent=2).encode("utf-8")


def _require_pojo_tree(value: object, annotation: object) -> None:
    """Check each record against the field type used by the V2 serializer."""
    if isinstance(value, RegistryKey):
        # The JSON reader reconstructs exactly RegistryKey, including for branded fields.
        if type(value) is not RegistryKey:
            raise ValueError("unexpected V2 registry key subclass")
        if not value:
            raise ValueError("empty V2 registry key")
    if isinstance(value, str):
        str.encode(value, "utf-8")
    elif isinstance(value, int) and value.bit_length() > 63:
        # Decimal conversion checks the interpreter limit used by json.loads.
        # The V2 model's JSON parser also limits the signed token independently.
        from_json(str(int(value)))
    if isinstance(value, dict):
        raise ValueError("unexpected dictionary in typed V2 manifest")
    if isinstance(value, BaseModel):
        if type(value) is not annotation and not (
                get_origin(annotation) is UnionType and type(value) in get_args(annotation)):
            raise ValueError("unexpected V2 record type")
        fields = vars(value)
        if fields.keys() != type(value).model_fields.keys():
            raise ValueError("incomplete or extra V2 record fields")
        for name, child in fields.items():
            _require_pojo_tree(child, type(value).model_fields[name].annotation)
        admitted = type(value).model_validate(fields, strict=True, context=TerritoryVolume.STRICT_BOUNDS)
        if any(type(original) is not type(getattr(admitted, name)) or original != getattr(admitted, name)
               for name, original in fields.items()):
            raise ValueError("V2 record changed under strict admission")
    elif isinstance(value, (tuple, list)):
        if get_origin(annotation) is not type(value):
            raise ValueError("unexpected V2 collection type")
        item_type = get_args(annotation)[0]
        for item in value:
            _require_pojo_tree(item, item_type)


def encode_candidate_manifest(manifest: WorldPackManifest) -> bytes:
    if type(manifest) is not WorldPackManifest or manifest.pack_version != SPATIAL_PACK_WIRE_VERSION:
        raise ValueError("candidate encoding requires V2")
    if type(manifest.spatial_roots) is not tuple or any(type(row) is not SpatialDomainRootRef for row in manifest.spatial_roots):
        raise ValueError("expected typed spatial root descriptors")
    _require_pojo_tree(manifest, WorldPackManifest)
    return manifest.model_dump_json(indent=2, warnings="error").encode("utf-8")
