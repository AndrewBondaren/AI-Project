"""SCH-RACE-TEMPLATE outline — global ``race_templates`` library body (WB-13)."""

from __future__ import annotations

import uuid
from typing import Any, Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class RaceTemplateOutline(BaseModel):
    """Wire/library body for one race template.

    Legacy aliases: ``race_uid`` → ``template_uid``, ``display_race`` → ``display_name``.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    template_uid: DefaultOnWire[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("template_uid", "race_uid"),
    )
    system_name: DefaultOnWire[str | None] = None
    display_name: DefaultOnWire[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("display_name", "display_race"),
    )
    created_at: DefaultOnWire[str | None] = None
    race_traits: DefaultOnWire[dict[str, Any] | None] = None
    male: DefaultOnWire[dict[str, Any] | None] = None
    female: DefaultOnWire[dict[str, Any] | None] = None
    asexual: DefaultOnWire[dict[str, Any] | None] = None
    both: DefaultOnWire[dict[str, Any] | None] = None

    @model_validator(mode="after")
    def _fill_identity(self) -> Self:
        uid = self.template_uid or str(uuid.uuid4())
        system = self.system_name or uid
        display = self.display_name or system
        if (
            uid == self.template_uid
            and system == self.system_name
            and display == self.display_name
        ):
            return self
        return self.model_copy(
            update={
                "template_uid": uid,
                "system_name": system,
                "display_name": display,
            },
        )
