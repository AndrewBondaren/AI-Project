"""One district type (+ optional subtype / pin) on a settlement or specialization."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.worldDistrictTemplateRegistry import (
    DistrictTemplateKey,
)


class TypicalDistrictRef(BaseModel):
    """tz_city_generation.md §1.2 — type ≠ drawing. Optional pin is a district template name."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    district_type: StrictOnWire[str]
    district_subtype: DefaultOnWire[str | None] = None
    system_name: DefaultOnWire[DistrictTemplateKey | None] = None

    @field_validator("system_name", mode="before")
    @classmethod
    def _blank_pin_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    def normalized_subtype(self) -> str | None:
        token = (self.district_subtype or "").strip()
        return token or None

    def matches_template(self, template: DistrictTemplateEntry) -> bool:
        if template.district_type != self.district_type:
            return False
        want = self.normalized_subtype()
        have = (template.district_subtype or "").strip() or None
        return want == have
