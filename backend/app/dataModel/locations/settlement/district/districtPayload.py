"""District type-stamped freeze — tz_locations §Payload per type."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.locations.settlement.district.districtTopologySlot import DistrictTopologySlot


class DistrictPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    district_topology: DefaultOnWire[DistrictTopologySlot | None] = None
