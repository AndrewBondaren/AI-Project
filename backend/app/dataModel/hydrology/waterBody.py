"""Physical water-body facts; shared system identity/lifecycle belongs to W/L."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.materials.worldMaterialRegistry import MaterialKey


class WaterBody(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    water_body_uid: StrictOnWire[str]
    location_uid: DefaultWhenMissing[str | None] = None
    kind: StrictOnWire[BasinKind]
    liquid: DefaultWhenMissing[StrictOnWire[MaterialKey]] = "water"
    declared_level: StrictOnWire[int]
    z_water_level: StrictOnWire[int]
    declared_basin_uid: DefaultWhenMissing[str | None] = None
    parent_system_uid: DefaultWhenMissing[str | None] = None

    @classmethod
    def default_liquid(cls) -> MaterialKey:
        return cls.model_fields["liquid"].default
