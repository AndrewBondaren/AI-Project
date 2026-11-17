"""Internal projection and identity functions over admitted Pack values."""

from app.dataModel.worldPack.encoding.metadataBindings import PACK_METADATA_SCHEMA
from app.dataModel.worldPack.meta.worldPackManifest import ChunkRefineRole
from app.dataModel.worldPack.preparation.addresses import (
    PackAssemblyAddress, PackAssemblyHeaderAddress, PackChunkAddress,
    PackTileMetadataAddress, PackChunkMetadataAddress, PackLocationMetadataAddress,
    PackSettlementMetadataAddress, PackRegionMetadataAddress,
)
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataValueInputSelector
from app.encoding.canonicalCodec import content_digest, encode


def metadata_projection(assembly: PackAssemblyInput, address: PackAssemblyAddress) -> object | None:
    """Return None for an absent row; admission owns diagnostics and uniqueness."""
    if isinstance(address, PackAssemblyHeaderAddress):
        return (assembly.last_l0_mode, assembly.fine_cells_per_map_cell,
                assembly.world_map_cells_per_tile, assembly.fine_cell_size,
                assembly.map_subsurface_depth, assembly.terrain_chunk_columns)
    if isinstance(address, (PackTileMetadataAddress, PackChunkMetadataAddress)):
        tile = next((row for row in assembly.tiles if (row.gx, row.gy) == (address.gx, address.gy)), None)
        if tile is None:
            return None
        if isinstance(address, PackTileMetadataAddress):
            return tile.gx, tile.gy, tile.climate_status, tile.wilderness_refine_status
        chunk = next((row for row in tile.chunks if (row.cx, row.cy) == (address.cx, address.cy)), None)
        return None if chunk is None else (chunk.cx, chunk.cy, chunk.refine_role)
    if isinstance(address, PackLocationMetadataAddress):
        return next((row for row in assembly.locations if row.location_uid == address.location_uid), None)
    if isinstance(address, PackSettlementMetadataAddress):
        return next((row for row in assembly.settlements if row.location_uid == address.location_uid), None)
    if isinstance(address, PackRegionMetadataAddress):
        return next((row for row in assembly.wilderness_regions if row.region_uid == address.region_uid), None)
    return None


def metadata_value_fingerprint(address: PackAssemblyAddress, projection: object) -> str:
    """Hash an admitted projection; caller checks presence before calling."""
    return content_digest(encode(("pack.metadata.value", address, projection), PACK_METADATA_SCHEMA)).hex()


def metadata_input_fingerprint(
    selector: PackMetadataValueInputSelector, value: PackChunkAddress | ChunkRefineRole | None,
) -> str:
    """Hash an admitted selected input; evidence/slot admission is separate."""
    return content_digest(encode(("pack.metadata.input", selector, value), PACK_METADATA_SCHEMA)).hex()
