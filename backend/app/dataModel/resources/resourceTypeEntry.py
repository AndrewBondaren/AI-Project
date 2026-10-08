"""One `worlds.resource_type_registry[]` row — N1-W-10. tz_locations.md § resources."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictEnumOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.resources.enums.resourceKind import ResourceKind


class ResourceTypeEntry(BaseModel):
    """Extractable resource instance. Kind is engine-closed; key is N+1."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_resource: StrictOnWire[str]
    resource_kind: StrictEnumOnWire[ResourceKind]
    display_name: DefaultWhenMissing[str | None] = None
    glossary_ref: DefaultWhenMissing[str | None] = None
    is_renewable: DefaultWhenMissing[bool] = False
    base_regen_per_tick: DefaultWhenMissing[Annotated[int, Field(ge=0)] | None] = constrained_field(default=None)
    default_yield: DefaultWhenMissing[int] = constrained_field(default=10, greater_equals=0)
    yield_item_uid: DefaultWhenMissing[str | None] = None
    tag_refs: DefaultWhenMissing[list[str]] = Field(default_factory=list)
