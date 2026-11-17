"""Explicit inputs to the accepted Pack metadata canonical binding."""

from app.dataModel.registryKey import RegistryKey
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.worldPack.preparation.addresses import (
    PackChunkAddress, PackAssemblyHeaderAddress, PackTileMetadataAddress,
    PackChunkMetadataAddress, PackLocationMetadataAddress,
    PackSettlementMetadataAddress, PackRegionMetadataAddress,
)
from app.dataModel.worldPack.preparation.assembly import PackLocationAssembly, PackSettlementAssembly
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry, RegionIndexBounds, WildernessRegionStatus
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataInputField, PackMetadataValueInputSelector


def vector_cases() -> dict[str, tuple[object, ...]]:
    role = PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.REFINE_ROLE)
    address = PackChunkAddress(kind="wilderness_chunk", gx=-2, gy=3, cx=1, cy=4)
    volume = TerritoryVolume(x0=-2, y0=3, z0=-4, x1=5, y1=6, z1=7)
    location = PackLocationAssembly(location_uid="place", territory_volume=volume, climate_status="fine")
    settlement = PackSettlementAssembly(location_uid="town", territory_volume=volume,
        structure_status="partial", packed_district_uids=("d2", "d1"))
    region = WildernessRegionEntry(region_uid="forest", entry_type=RegistryKey[WorldTerrainRegistry]("forest"),
        current_type=RegistryKey[WorldTerrainRegistry]("forest"),
        bbox=RegionIndexBounds(x_min=-2, y_min=3, x_max=5, y_max=6),
        status=WildernessRegionStatus.DECLARED, parent_region_uid=None, spec_fingerprint=None)
    return {
        "address": ("pack.metadata.input", PackMetadataValueInputSelector(kind="value", field=PackMetadataInputField.ADDRESS), address),
        "role_none": ("pack.metadata.input", role, None),
        "role_scene": ("pack.metadata.input", role, "scene"),
        "role_background": ("pack.metadata.input", role, "background"),
        "role_path": ("pack.metadata.input", role, "path"),
        "role_location": ("pack.metadata.input", role, "location"),
        "header": ("pack.metadata.value", PackAssemblyHeaderAddress(kind="header"), ("light", 1000, 32, 1, 0, 32)),
        "tile_coarse": ("pack.metadata.value", PackTileMetadataAddress(kind="tile", gx=-2, gy=3), (-2, 3, "coarse", "partial")),
        "tile_fine": ("pack.metadata.value", PackTileMetadataAddress(kind="tile", gx=-2, gy=3), (-2, 3, "fine", "complete")),
        "chunk": ("pack.metadata.value", PackChunkMetadataAddress(kind="chunk", gx=-2, gy=3, cx=1, cy=4), (1, 4, None)),
        "location": ("pack.metadata.value", PackLocationMetadataAddress(kind="location", location_uid="place"), location),
        "settlement": ("pack.metadata.value", PackSettlementMetadataAddress(kind="settlement", location_uid="town"), settlement),
        "region": ("pack.metadata.value", PackRegionMetadataAddress(kind="region", region_uid="forest"), region),
    }


def encoded_vectors() -> dict[str, dict[str, str]]:
    from app.encoding.canonicalCodec import content_digest, encode
    from app.dataModel.worldPack.encoding.metadataBindings import PACK_METADATA_SCHEMA
    result: dict[str, dict[str, str]] = {}
    for name, value in vector_cases().items():
        encoded = encode(value, PACK_METADATA_SCHEMA)
        result[name] = {"hex": encoded.hex(), "sha256": content_digest(encoded).hex()}
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(encoded_vectors(), sort_keys=True))
