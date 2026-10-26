"""Explicit snapshot selector and derive-on-read outline response contracts."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry


class WildernessRegionSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    snapshot: Literal[True] = True
    entry: WildernessRegionEntry


class WildernessRegionOutline(BaseModel):
    model_config = ConfigDict(frozen=True)
    region_uid: str
    source: Literal["derived_world_data"] = "derived_world_data"
    resolution: Literal["L0"] = "L0"
    outline: str
