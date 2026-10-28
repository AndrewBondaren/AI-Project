"""Resolved transport metadata; source mapping and default resolution live outside."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSourceKind
from app.dataModel.identity.uid import EntityUid
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.spatial.grid.coordinateTypes import FineZ


class WaterSourceMetadata(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    source_uid: EntityUid
    source_kind: WaterDesignSourceKind
    body_kind: BasinKind
    liquid: MaterialKey
    level: FineZ
    bands: HydrologyBands
    source_path: tuple[str | int, ...]
    default_depth: StrictInt = Field(gt=0)

    @field_validator("bands", mode="before")
    @classmethod
    def revalidate_bands(cls, value: object) -> object:
        return value.model_dump(warnings=False) if isinstance(value, HydrologyBands) else value

    @model_validator(mode="after")
    def ordered_bands(self) -> Self:
        if self.bands.min > self.bands.max:
            raise ValueError("water source bands require min <= max")
        return self
