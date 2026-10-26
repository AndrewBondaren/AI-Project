"""Typed reads from the location's payload storage."""

from pydantic import BaseModel
from app.application.jsonValidation.resolve import ResolveContext, resolve_model

from app.dataModel.locations.locationPayload import LocationPayload
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.locations.settlement.district.districtPayload import DistrictPayload


def _read(location: object, model: type[BaseModel], ctx: ResolveContext | None = None):
    raw = getattr(location, "location_payload", None)
    return resolve_model(model, {} if raw is None else raw,
                         ctx=ctx if ctx is not None else ResolveContext(path_prefix=("locations", getattr(location, "location_uid", "?"), "location_payload")))


def settlement_payload(location: object, *, ctx: ResolveContext | None = None) -> SettlementPayload:
    return _read(location, SettlementPayload, ctx)


def district_payload(location: object) -> DistrictPayload:
    return _read(location, DistrictPayload)


def payload_field_names() -> frozenset[str]:
    return frozenset(name for model in LocationPayload.models().values()
                     for name in model.model_fields)
