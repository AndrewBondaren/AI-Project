"""Physical producer facts; W/L owns lifecycle records and their persistence."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire


class PhysicalWaterUnion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    water_system_uid: StrictOnWire[str]
    member_uids: StrictOnWire[tuple[str, ...]]
    child_system_uids: StrictOnWire[tuple[str, ...]]
    z_water_level: StrictOnWire[int]
    parent_system_uid: DefaultWhenMissing[str | None] = None
