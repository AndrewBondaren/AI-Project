"""SCH-RACE-TEMPLATE outline — global ``race_templates`` library body (WB-13)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire


class RaceTemplateOutline(BaseModel):
    """Wire/library body for one race template.

    Legacy aliases: ``race_uid`` → ``template_uid``, ``display_race`` → ``display_name``.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    template_uid: DefaultWhenMissing[Annotated[str, Field(min_length=1)] | None] = Field(
        default=None,
        validation_alias=AliasChoices("template_uid", "race_uid"),
    )
    system_name: DefaultWhenMissing[Annotated[str, Field(min_length=1)] | None] = None
    display_name: DefaultWhenMissing[Annotated[str, Field(min_length=1)] | None] = Field(
        default=None,
        validation_alias=AliasChoices("display_name", "display_race"),
    )
    created_at: DefaultWhenMissing[str | None] = None
    race_traits: DefaultWhenMissing[dict[str, Any] | None] = None
    male: DefaultWhenMissing[dict[str, Any] | None] = None
    female: DefaultWhenMissing[dict[str, Any] | None] = None
    asexual: DefaultWhenMissing[dict[str, Any] | None] = None
    both: DefaultWhenMissing[dict[str, Any] | None] = None

    @model_validator(mode="after")
    def _fill_identity(self) -> Self:
        uid = str(uuid.uuid4()) if self.template_uid is None else self.template_uid
        system = uid if self.system_name is None else self.system_name
        display = system if self.display_name is None else self.display_name
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
