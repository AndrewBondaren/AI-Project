"""Named inputs of individual Pack composition operations."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.worldPack.preparation.addresses import PackPartAddress, PackLocationTerrainAddress, PackSettlementAddress
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldPack.preparation.parts import PackCoarseClimatePartInput, PackLocationsIndexPartInput


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
