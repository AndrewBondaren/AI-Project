"""Whole-element operations on the declared collection, keyed by name."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.dataModel.terrainMasks.regions import LandcoverDeclareEntry
from app.ids.regionIdentity import normalize_region_name


class RegionEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str) -> str:
        name = normalize_region_name(value)
        if name is None:
            raise ValueError("region operation requires a name")
        return name


class AddRegion(RegionEdit):
    op: Literal["add"]
    region: LandcoverDeclareEntry


class UpdateRegion(RegionEdit):
    op: Literal["update"]
    region: LandcoverDeclareEntry


class RemoveRegion(RegionEdit):
    op: Literal["remove"]


DeclaredRegionEdit = Annotated[AddRegion | UpdateRegion | RemoveRegion, Field(discriminator="op")]
