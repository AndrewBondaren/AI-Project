"""Canonical registration of Pack metadata values and input selectors."""
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind, RegisteredTypeEntry
from app.dataModel.worldPack.preparation.addresses import (
    PackChunkAddress, PackAssemblyHeaderAddress, PackTileMetadataAddress,
    PackChunkMetadataAddress, PackLocationMetadataAddress,
    PackSettlementMetadataAddress, PackRegionMetadataAddress,
)
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataValueInputSelector, PackMetadataInputField
from app.dataModel.worldPack.preparation.assembly import PackLocationAssembly, PackSettlementAssembly
from app.dataModel.worldPack.wire.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry, RegionIndexBounds, WildernessRegionStatus

PACK_METADATA_SCHEMA = CanonicalSchemaManifest(entries=(
    RegisteredTypeEntry(type_id=20401, python_type=PackChunkAddress, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20402, python_type=PackAssemblyHeaderAddress, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20403, python_type=PackTileMetadataAddress, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20404, python_type=PackChunkMetadataAddress, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20405, python_type=PackLocationMetadataAddress, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20406, python_type=PackSettlementMetadataAddress, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20407, python_type=PackRegionMetadataAddress, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20408, python_type=PackMetadataValueInputSelector, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20409, python_type=PackMetadataInputField, kind=CanonicalTypeKind.ENUM),
    RegisteredTypeEntry(type_id=20410, python_type=PackLocationAssembly, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20411, python_type=PackSettlementAssembly, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20412, python_type=TerritoryVolume, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20413, python_type=WildernessRegionEntry, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20414, python_type=RegionIndexBounds, kind=CanonicalTypeKind.RECORD),
    RegisteredTypeEntry(type_id=20415, python_type=WildernessRegionStatus, kind=CanonicalTypeKind.ENUM),
))

