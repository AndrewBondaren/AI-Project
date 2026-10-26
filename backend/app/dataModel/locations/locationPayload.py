"""Builtin payload model registry — selected by contract, not location type."""

from typing import Any

from pydantic import BaseModel

from app.dataModel.locations.payloadKind import PayloadKind


class LocationPayload:
    @classmethod
    def models(cls) -> dict[PayloadKind, type[BaseModel]]:
        # Lazy domain imports keep location-type metadata independent of
        # settlement/structure package initialization.
        from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
        from app.dataModel.locations.settlement.district.districtPayload import DistrictPayload

        return {
            PayloadKind.SETTLEMENT: SettlementPayload,
            PayloadKind.DISTRICT: DistrictPayload,
        }

    @classmethod
    def model_for(cls, kind: PayloadKind | str) -> type[BaseModel]:
        return cls.models()[PayloadKind(kind)]

    @classmethod
    def validate(cls, kind: PayloadKind | str | None, value: Any) -> BaseModel | None:
        if kind is None:
            if value is not None:
                raise ValueError("location type without payload_kind cannot carry a payload")
            return None
        return cls.model_for(kind).model_validate({} if value is None else value)
