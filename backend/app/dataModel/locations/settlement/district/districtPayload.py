"""District type-stamped freeze — tz_locations §Payload per type."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.locations.settlement.district.districtTopologySlot import DistrictTopologySlot


class DistrictPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    district_topology: DefaultWhenMissing[DistrictTopologySlot | None] = None
