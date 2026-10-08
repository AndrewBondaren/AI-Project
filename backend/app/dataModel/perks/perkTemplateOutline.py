"""SCH-PERK-TEMPLATE outline — global ``perk_templates`` library body (WB-14).

Stub fields match ``WorldPerk`` / SQL; full perk schema may grow later.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing


class PerkTemplateOutline(BaseModel):
    """Wire/library body for one perk template.

    Legacy alias: ``perk_uid`` → ``template_uid``.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    template_uid: DefaultWhenMissing[Annotated[str, Field(min_length=1)] | None] = Field(
        default=None,
        validation_alias=AliasChoices("template_uid", "perk_uid"),
    )
    system_name: DefaultWhenMissing[Annotated[str, Field(min_length=1)] | None] = None
    display_name: DefaultWhenMissing[Annotated[str, Field(min_length=1)] | None] = None
    system_description: DefaultWhenMissing[str | None] = None
    display_description: DefaultWhenMissing[str | None] = None
    system_rank_value: DefaultWhenMissing[list[Any] | None] = None
    display_rank_value: DefaultWhenMissing[str | None] = None
    system_tags: DefaultWhenMissing[list[Any] | None] = None
    display_tags: DefaultWhenMissing[str | None] = None
    system_condition: DefaultWhenMissing[str | None] = None
    display_condition: DefaultWhenMissing[str | None] = None
    terrain_access: DefaultWhenMissing[list[Any] | None] = None

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
