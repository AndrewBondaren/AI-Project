"""Typed payload reads; legacy column fallback is removed in P2b."""

from pydantic import BaseModel

from app.dataModel.locations.locationPayload import LocationPayload
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.locations.settlement.district.districtPayload import DistrictPayload


def _read(location: object, model: type[BaseModel]):
    raw = getattr(location, "location_payload", None)
    if raw is None:
        raw = {name: getattr(location, name) for name in model.model_fields
               if getattr(location, name, None) is not None}
    return model.model_validate(raw)


def settlement_payload(location: object) -> SettlementPayload:
    return _read(location, SettlementPayload)


def district_payload(location: object) -> DistrictPayload:
    return _read(location, DistrictPayload)


def payload_field_names() -> frozenset[str]:
    return frozenset(name for model in LocationPayload.models().values()
                     for name in model.model_fields)


def source_wire(location: object, wire: dict) -> dict:
    """P3 bridge: stored payload supplies the old NL cascade nodes until P4."""
    raw = getattr(location, "location_payload", None)
    if raw is not None:
        for name in payload_field_names():
            wire.pop(name, None)
        wire.update(raw)
    return wire
