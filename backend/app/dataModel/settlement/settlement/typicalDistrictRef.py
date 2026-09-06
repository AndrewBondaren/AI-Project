"""One district type (+ optional subtype / pin) on a settlement or specialization."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry


class TypicalDistrictRef(BaseModel):
    """tz_city_generation.md §1.2 — type ≠ drawing. Optional pin is a district template name."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    district_type: StrictOnWire[str]
    district_subtype: DefaultOnWire[str | None] = None
    system_name: DefaultOnWire[str | None] = None

    def normalized_subtype(self) -> str | None:
        token = (self.district_subtype or "").strip()
        return token or None

    def matches_template(self, template: DistrictTemplateEntry) -> bool:
        if template.district_type != self.district_type:
            return False
        want = self.normalized_subtype()
        have = (template.district_subtype or "").strip() or None
        return want == have
