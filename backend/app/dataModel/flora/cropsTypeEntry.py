"""One `worlds.crops_registry[]` row — N1-W-11. Farm subjects; morphology later (tz_flora)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire, StrictOnWire
from app.dataModel.flora.enums.cropKind import CropKind


class CropsTypeEntry(BaseModel):
    """Cultivated crop instance. Kind is engine-closed; key is N+1."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_crop: StrictOnWire[str]
    crop_kind: StrictEnumOnWire[CropKind]
    display_name: DefaultOnWire[str | None] = None
    glossary_ref: DefaultOnWire[str | None] = None
