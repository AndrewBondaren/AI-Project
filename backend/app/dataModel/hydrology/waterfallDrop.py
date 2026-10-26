"""Physical vertical-step fact, independent of river type/rapids classification."""

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.topology.worldTopology import Coord


class WaterfallDrop(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    upper_cell: Coord
    lower_cell: Coord
    upper_z: int
    lower_z: int
    liquid: DefaultWhenMissing[MaterialKey] = "water"
    connection_edge_uid: DefaultWhenMissing[str | None] = None

    @model_validator(mode="after")
    def positive_drop(self):
        if self.upper_z <= self.lower_z:
            raise ValueError("waterfall drop requires upper_z > lower_z")
        return self

    @property
    def height(self) -> int:
        return self.upper_z - self.lower_z
