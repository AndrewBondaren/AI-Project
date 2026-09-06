"""One `worlds.settlement_specialization_registry[]` row — tz_city_generation.md §4.1."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.settlement.settlement.typicalDistrictRef import TypicalDistrictRef


class SettlementSpecializationEntry(BaseModel):
    """Role recipe: districts, default buildings, optional subject → extra structure_type."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_specialization: StrictOnWire[str]
    display_specialization: DefaultOnWire[str | None] = None
    # N+1 kind label(s), not a closed enum: resource, material, crop, product, domain, …
    # Wire: string, list, or alias ``subject_kinds``.
    # TODO(specialization-subjects): extract → resource_type_registry;
    # farm → crops_registry (building ``crop_kind`` is ENUM-E);
    # livestock → livestock_registry (building ``livestock_kind`` is ENUM-E).
    # Product / domain catalogs are not wired yet. See SettlementSpecializationBind.
    subject_kind: DefaultOnWire[str | list[str] | None] = None
    typical_districts: DefaultOnWire[list[TypicalDistrictRef]] = Field(default_factory=list)
    required_structure_types: DefaultOnWire[list[str]] = Field(default_factory=list)
    subjects_to_structure_types: DefaultOnWire[dict[str, list[str]]] = Field(
        default_factory=dict,
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_subject_kind(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "subject_kind" in data or "subject_kinds" not in data:
            return data
        payload = dict(data)
        payload["subject_kind"] = payload.get("subject_kinds")
        return payload

    def kind_keys(self) -> tuple[str, ...]:
        """Declared subject kinds for this role (one or several)."""
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

    def resolved_structure_types(self, subjects: Sequence[str]) -> tuple[str, ...]:
        """Empty subjects → role defaults. Mapped subjects replace defaults; unknown keep defaults."""
        wanted = [token.strip() for token in subjects if token and token.strip()]
        if not wanted:
            return tuple(self.required_structure_types)
        mapped: list[str] = []
        seen: set[str] = set()
        known = 0
        for subject in wanted:
            types = self.subjects_to_structure_types.get(subject) or []
            if types:
                known += 1
            for structure_type in types:
                if structure_type in seen:
                    continue
                seen.add(structure_type)
                mapped.append(structure_type)
        if known:
            return tuple(mapped)
        return tuple(self.required_structure_types)
