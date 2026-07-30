"""SCH-PERK-TEMPLATE outline — global ``perk_templates`` library body (WB-14).

Stub fields match ``WorldPerk`` / SQL; full perk schema may grow later.
"""

from __future__ import annotations

import uuid
from typing import Any, Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire


class PerkTemplateOutline(BaseModel):
    """Wire/library body for one perk template.

    Legacy alias: ``perk_uid`` → ``template_uid``.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    template_uid: DefaultOnWire[str | None] = Field(
        default=None,
        validation_alias=AliasChoices("template_uid", "perk_uid"),
    )
    system_name: DefaultOnWire[str | None] = None
    display_name: DefaultOnWire[str | None] = None
    system_description: DefaultOnWire[str | None] = None
    display_description: DefaultOnWire[str | None] = None
    system_rank_value: DefaultOnWire[list[Any] | None] = None
    display_rank_value: DefaultOnWire[str | None] = None
    system_tags: DefaultOnWire[list[Any] | None] = None
    display_tags: DefaultOnWire[str | None] = None
    system_condition: DefaultOnWire[str | None] = None
    display_condition: DefaultOnWire[str | None] = None
    terrain_access: DefaultOnWire[list[Any] | None] = None

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
