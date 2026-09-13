"""One `worlds.settlement_specialization_registry[]` row — tz_city_generation.md §4.1."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire, StrictOnWire
from app.dataModel.registryKey import RegistryKey
from app.dataModel.settlement.settlement.typicalDistrictRef import TypicalDistrictRef
from app.dataModel.structure.enums.buildingPurpose.family import BuildingPurposeFamily

if TYPE_CHECKING:
    from app.dataModel.settlement.settlement.worldSettlementSpecializationRegistry import (
        WorldSettlementSpecializationRegistry,
    )

_DEAD_KEYS = ("required_structure_types", "subjects_to_structure_types")


class SettlementSpecializationEntry(BaseModel):
    """Specialization recipe: districts + one purpose family. Leaves come from the world."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_specialization: StrictOnWire[RegistryKey[WorldSettlementSpecializationRegistry]]
    display_specialization: DefaultOnWire[str | None] = None
    # N+1 kind label(s), not a closed enum: resource, material, crop, product, domain, …
    # Wire: string, list, or alias ``subject_kinds``.
    # TODO(specialization-subjects): extract → resource_type_registry;
    # farm → crops_registry (building ``crop_kind`` is ENUM-E);
    # livestock → livestock_registry (building ``livestock_kind`` is ENUM-E).
    # Product / domain catalogs are not wired yet. See SettlementSpecializationBind.
    subject_kind: DefaultOnWire[str | list[str] | None] = None
    typical_districts: DefaultOnWire[list[TypicalDistrictRef]] = Field(default_factory=list)
    allowed_family: StrictEnumOnWire[BuildingPurposeFamily]

    @model_validator(mode="before")
    @classmethod
    def _coerce_wire(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        dead = [key for key in _DEAD_KEYS if key in data]
        if dead:
            raise ValueError(
                "SettlementSpecializationEntry rejected "
                + ", ".join(dead)
                + "; use allowed_family"
            )
        if "subject_kind" in data or "subject_kinds" not in data:
            return data
        payload = dict(data)
        payload["subject_kind"] = payload.get("subject_kinds")
        return payload

    @field_validator("allowed_family", mode="before")
    @classmethod
    def _family_not_leaf(cls, value: Any) -> Any:
        family = BuildingPurposeFamily.from_wire(value)
        if family is None:
            raise ValueError(
                "allowed_family must be a BuildingPurposeFamily, not a leaf"
            )
        return family

    def kind_keys(self) -> tuple[str, ...]:
        """Declared subject kinds for this specialization (one or several)."""
        raw = self.subject_kind
        if raw is None:
            return ()
        if isinstance(raw, str):
            token = raw.strip()
            return (token,) if token else ()
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, str):
                continue
            token = item.strip()
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
        return tuple(out)
