"""Named payload inputs with one declaration of address, ref and provenance."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.worldPack.preparation.addresses import (
    PackChunkAddress, PackCoarseClimateAddress, PackFineClimateAddress,
    PackLocationGradeSlotsAddress, PackLocationTerrainAddress,
    PackLocationsIndexAddress, PackMapTileAddress, PackPartAddress,
    PackSettlementAddress, PackSpatialRootAddress, PackTileGradeSlotsAddress,
)
from app.dataModel.worldPack.preparation.provenance import PackPartProvenance


AddressT = TypeVar("AddressT", bound=PackPartAddress)


class _PackPartInput(BaseModel, Generic[AddressT]):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    address: AddressT
    artifact: ArtifactRef
    provenance: PackPartProvenance


class PackPartInput(_PackPartInput[PackPartAddress]):
    pass


class PackMapTilePartInput(_PackPartInput[PackMapTileAddress]):
    pass


class PackWildernessChunkPartInput(_PackPartInput[PackChunkAddress]):
    pass


class PackLocationTerrainPartInput(_PackPartInput[PackLocationTerrainAddress]):
    pass


class PackSettlementStructurePartInput(_PackPartInput[PackSettlementAddress]):
    pass


class PackCoarseClimatePartInput(_PackPartInput[PackCoarseClimateAddress]):
    pass


class PackFineClimatePartInput(_PackPartInput[PackFineClimateAddress]):
    pass


class PackLocationsIndexPartInput(_PackPartInput[PackLocationsIndexAddress]):
    pass


class PackTileGradeSlotsPartInput(_PackPartInput[PackTileGradeSlotsAddress]):
    pass


class PackLocationGradeSlotsPartInput(_PackPartInput[PackLocationGradeSlotsAddress]):
    pass


class PackSpatialRootPartInput(_PackPartInput[PackSpatialRootAddress]):
    pass
