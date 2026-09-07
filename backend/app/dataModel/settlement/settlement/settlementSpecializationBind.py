"""One specialization bind on a settlement template — role + N+1 subjects."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.settlement.settlement.worldSettlementSpecializationRegistry import (
    SettlementSpecializationKey,
)


def _token(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _unique_tokens(values: Any) -> list[str]:
    seq = values if isinstance(values, list) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in seq:
        token = _token(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


class SettlementSpecializationBind(BaseModel):
    """
    Instance overlay: which role this place lives by, and optional subjects
    (ores, crops, products, knowledge/religion domains, materials, …). N+1 strings.

    Wire: object or a bare role string (``\"extract\"`` → empty subjects).
    ``subjects`` is a flat list **or** a map of kind → tokens
    (``{\"resource\": [\"iron_ore\", \"copper_ore\"]}``).

    TODO(specialization-subjects): extract tokens → ``resource_type_registry``;
    farm tokens → ``crops_registry`` (``CropKind`` on the crop row and on the
    building template ``crop_kind``); livestock tokens → ``livestock_registry``
    (``LivestockKind`` on the animal row and on the building template
    ``livestock_kind``). Product / domain catalogs are not wired yet.
    Location-bind REF-W is not wired yet; building templates with
    ``resource_kind`` / ``crop_kind`` / ``livestock_kind`` are checked on library import.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_specialization: StrictOnWire[SettlementSpecializationKey]
    subjects: DefaultOnWire[list[str]] = Field(default_factory=list)
    # Filled when wire ``subjects`` is a kind → tokens map; omitted on dump.
    subject_groups: DefaultOnWire[dict[str, list[str]]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_string_or_mapping(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"system_specialization": data}
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        raw = payload.get("subjects")
        if isinstance(raw, dict):
            groups: dict[str, list[str]] = {}
            flat: list[str] = []
            seen: set[str] = set()
            for kind, values in raw.items():
                kind_key = _token(kind)
                if not kind_key:
                    continue
                tokens = _unique_tokens(values)
                if not tokens:
                    continue
                groups[kind_key] = tokens
                for token in tokens:
                    if token in seen:
                        continue
                    seen.add(token)
                    flat.append(token)
            payload["subjects"] = flat
            payload["subject_groups"] = groups
        elif isinstance(raw, str):
            token = _token(raw)
            payload["subjects"] = [token] if token else []
        return payload

    @model_serializer(mode="wrap")
    def _dump_subjects_wire(self, handler):
        data = handler(self)
        groups = {
            kind: list(tokens)
            for kind, tokens in (self.subject_groups or {}).items()
            if kind and tokens
        }
        if groups:
            data["subjects"] = groups
        data.pop("subject_groups", None)
        return data

    def subject_keys(self) -> tuple[str, ...]:
        return tuple(token.strip() for token in self.subjects if token and token.strip())

    def subjects_by_kind(self) -> dict[str, tuple[str, ...]]:
        return {
            kind: tuple(tokens)
            for kind, tokens in (self.subject_groups or {}).items()
            if kind and tokens
        }
