"""Typed reads from the location's payload storage."""

from pydantic import BaseModel

from app.dataModel.locations.locationPayload import LocationPayload
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.locations.settlement.district.districtPayload import DistrictPayload


def _read(location: object, model: type[BaseModel]):
    raw = getattr(location, "location_payload", None)
    return model.model_validate({} if raw is None else raw)


def settlement_payload(location: object) -> SettlementPayload:
    return _read(location, SettlementPayload)


def district_payload(location: object) -> DistrictPayload:
    return _read(location, DistrictPayload)


def payload_field_names() -> frozenset[str]:
    return frozenset(name for model in LocationPayload.models().values()
                     for name in model.model_fields)
