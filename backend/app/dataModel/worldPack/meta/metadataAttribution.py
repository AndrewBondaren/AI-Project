"""Durable group attribution within a single metadata row's Source proof."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.sourceVersioning.sourceProofSelection import SourceProofSelection
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.worldPack.preparation.addresses import PackAssemblyAddress, PackChunkAddress
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance


class PackMetadataGroup(StrEnum):
    LAST_L0_MODE = "last_l0_mode"
    FINE_CELLS_PER_MAP_CELL = "fine_cells_per_map_cell"
    WORLD_MAP_CELLS_PER_TILE = "world_map_cells_per_tile"
    FINE_CELL_SIZE = "fine_cell_size"
    MAP_SUBSURFACE_DEPTH = "map_subsurface_depth"
    TERRAIN_CHUNK_COLUMNS = "terrain_chunk_columns"
    IDENTITY = "identity"
    CLIMATE_STATUS = "climate_status"
    WILDERNESS_REFINE_STATUS = "wilderness_refine_status"
    REFINE_ROLE = "refine_role"
    TERRITORY_VOLUME = "territory_volume"
    PACKED_DISTRICT_UIDS = "packed_district_uids"
    STRUCTURE_STATUS = "structure_status"
    ENTRY_TYPE = "entry_type"
    CURRENT_TYPE = "current_type"
    BBOX = "bbox"
    REGION_STATUS = "region_status"
    PARENT_REGION_UID = "parent_region_uid"
    SPEC_FINGERPRINT = "spec_fingerprint"


class _PackMetadataValue(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    @model_validator(mode="after")
    def immutable_value(self) -> Self:
        validate_immutable(self)
        return self


class PackWildernessStatusBasis(_PackMetadataValue):
    chunk_addresses: tuple[PackChunkAddress, ...]
    expected_chunks: int | None


class PackMetadataGroupAdmission(_PackMetadataValue):
    group: PackMetadataGroup
    selection: SourceProofSelection
    basis: PackWildernessStatusBasis | None


class PackMetadataAttribution(_PackMetadataValue):
    groups: tuple[PackMetadataGroupAdmission, ...]


class PackStoredAssemblyProvenance(_PackMetadataValue):
    address: PackAssemblyAddress
    provenance: PackStoredProvenance
    attribution: PackMetadataAttribution | None
