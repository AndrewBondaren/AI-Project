"""Transient metadata usage carried between explicit Pack operations."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StrictInt

from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.worldPack.meta.metadataAttribution import (
    PackMetadataGroup, PackWildernessStatusBasis, _PackMetadataValue,
)
from app.dataModel.worldPack.preparation.metadataSubject import PackMetadataSubject


class PackMetadataDependencyUse(_PackMetadataValue):
    group: PackMetadataGroup
    source_usage: SourceProofInput
    basis: PackWildernessStatusBasis | None


class PackMetadataDescription(_PackMetadataValue):
    subject: PackMetadataSubject
    dependencies: tuple[PackMetadataDependencyUse, ...]


class PackMetadataInputField(StrEnum):
    ADDRESS = "address"
    FINE_CELLS_PER_MAP_CELL = "fine_cells_per_map_cell"
    WORLD_MAP_CELLS_PER_TILE = "world_map_cells_per_tile"
    FINE_CELL_SIZE = "fine_cell_size"
    MAP_SUBSURFACE_DEPTH = "map_subsurface_depth"
    TERRAIN_CHUNK_COLUMNS = "terrain_chunk_columns"
    MODE = "mode"
    EFFECTIVE_SIDE = "effective_side"
    REFINE_ROLE = "refine_role"
    TERRITORY_VOLUME = "territory_volume"
    PACKED_DISTRICT_UIDS = "packed_district_uids"
    STRUCTURE_STATUS = "structure_status"
    EXPECTED_CHUNKS = "expected_chunks"


class PackRegionMetadataInputField(StrEnum):
    REGION_UID = "region_uid"
    ENTRY_TYPE = "entry_type"
    CURRENT_TYPE = "current_type"
    BBOX = "bbox"
    STATUS = "status"
    PARENT_REGION_UID = "parent_region_uid"
    SPEC_FINGERPRINT = "spec_fingerprint"


class PackMetadataValueInputSelector(_PackMetadataValue):
    kind: Literal["value"]
    field: PackMetadataInputField


class PackMetadataRegionInputSelector(_PackMetadataValue):
    kind: Literal["region_entry"]
    entry_index: Annotated[StrictInt, Field(ge=0)]
    field: PackRegionMetadataInputField


PackMetadataInputSelector = Annotated[
    PackMetadataValueInputSelector | PackMetadataRegionInputSelector,
    Field(discriminator="kind"),
]


class PackMetadataInputEvidence(_PackMetadataValue):
    input: PackMetadataInputSelector
    value_fingerprint: RevisionHex
    source_usage: SourceProofInput
