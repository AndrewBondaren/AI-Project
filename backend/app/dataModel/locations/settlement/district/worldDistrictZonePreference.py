"""Root POJO for ``worlds.district_zone_preference`` — CITY-T-4e."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire
from app.dataModel.settlement.district.cellZone import CellZone


class DistrictZonePreferenceEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    zone: StrictEnumOnWire[CellZone]
    district_types: DefaultOnWire[list[str]] = Field(default_factory=list)


_CANONICAL_ENTRIES: tuple[DistrictZonePreferenceEntry, ...] = (
    DistrictZonePreferenceEntry(
        zone=CellZone.CENTER,
        district_types=["civic", "commercial", "residential"],
    ),
    DistrictZonePreferenceEntry(
        zone=CellZone.EDGE,
        district_types=["port", "agricultural", "commercial", "residential", "industrial"],
    ),
    DistrictZonePreferenceEntry(
        zone=CellZone.INNER,
        district_types=["residential", "commercial", "industrial", "agricultural"],
    ),
)


class WorldDistrictZonePreference(RootModel[list[DistrictZonePreferenceEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-DISTRICT-ZONE"
    RUNTIME_MERGE_ID_FIELD: ClassVar[str] = "zone"
    root: list[DistrictZonePreferenceEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldDistrictZonePreference:
        return cls(list(_CANONICAL_ENTRIES))

    def types_for(self, zone: CellZone | str) -> tuple[str, ...]:
        try:
            key = zone if isinstance(zone, CellZone) else CellZone(str(zone))
        except ValueError:
            return ()
        for entry in self.root:
            if entry.zone == key:
                return tuple(entry.district_types)
        return ()
