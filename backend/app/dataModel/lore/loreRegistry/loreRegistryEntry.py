"""One `worlds.lore_registry` map value — N1-W-21 stub body."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire


class LoreRegistryEntry(BaseModel):
    """tz_json_validation.md N1-W-21 — glossary target; full contract deferred to tz_lore."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    display_name: StrictOnWire[str]
    description: DefaultWhenMissing[str | None] = None

    @model_validator(mode="before")
    @classmethod
    def _reject_removed_keys(cls, data):
        """Removed keys read as an error, not a silent drop."""
        if isinstance(data, dict):
            for old in ("title", "content"):
                if old in data:
                    raise ValueError(f"{old} was removed; use display_name/description")
        return data
