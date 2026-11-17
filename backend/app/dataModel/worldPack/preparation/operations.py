"""Named inputs of individual Pack composition operations."""

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict

from app.dataModel.worldPack.preparation.addresses import PackPartAddress, PackLocationTerrainAddress, PackSettlementAddress
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldPack.preparation.parts import PackCoarseClimatePartInput, PackLocationsIndexPartInput
from app.dataModel.worldPack.preparation.parts import PackSpatialRootPartInput
from app.dataModel.worldPack.preparation.parts import PackTileGradeSlotsPartInput, PackLocationGradeSlotsPartInput
from app.dataModel.worldPack.preparation.assembly import PackAssemblyInput
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldPack.meta.worldPackManifest import ChunkRefineRole
from app.dataModel.worldPack.preparation.parts import PackWildernessChunkPartInput
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataInputEvidence


class PackPreparationEmptyInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    base_publication: WorldPublicationRef
    initial_assembly: PackAssemblyInput


class PackWildernessChunkWrite(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    part: PackWildernessChunkPartInput
    refine_role: ChunkRefineRole | None
    metadata_inputs: tuple[PackMetadataInputEvidence, ...]


class PackWildernessChunkInput(PackWildernessChunkWrite):
    state: PackPreparationState


def _exact_chunk_item(value: object) -> object:
    if isinstance(value, PackWildernessChunkWrite) and type(value) is not PackWildernessChunkWrite:
        raise ValueError("batch entry requires the exact chunk write item")
    return value


class PackWildernessChunksInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    entries: tuple[Annotated[PackWildernessChunkWrite, BeforeValidator(_exact_chunk_item)], ...]


class PackDeletePartInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    address: PackPartAddress


class PackDeleteLocationTerrainInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    address: PackLocationTerrainAddress


class PackDeleteSettlementStructureInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    address: PackSettlementAddress


class PackCoarseClimateInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    part: PackCoarseClimatePartInput


class PackLocationsIndexInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    part: PackLocationsIndexPartInput


class PackSpatialRootInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    part: PackSpatialRootPartInput


class PackTileGradeSlotsInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    part: PackTileGradeSlotsPartInput


class PackLocationGradeSlotsInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    state: PackPreparationState
    part: PackLocationGradeSlotsPartInput
