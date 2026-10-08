"""One ``worlds.purpose_pack_registry[]`` row — tz_building_generator.md §2.1."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.registryKey import RegistryKey
from app.dataModel.locations.structure.enums.buildingPurpose.catalog import (
    AllowedToken,
    coerce_allowed_list,
)
from app.dataModel.locations.structure.enums.buildingPurpose.packs import normalize_pack_id

if TYPE_CHECKING:
    from app.dataModel.locations.structure.enums.buildingPurpose.worldPurposePackRegistry import (
        WorldPurposePackRegistry,
    )

def _wire_pack_id(value: Any) -> Any:
    token = normalize_pack_id(value)
    return token if token is not None else value


def _wire_pack_allowed(value: Any) -> Any:
    if value is None:
        return value
    items: list[object]
    if isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [value]
    return coerce_allowed_list(items)


class PurposePackEntry(BaseModel):
    """Pack recipe: which known families/leaves this mask turns on."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_pack: StrictOnWire[
        Annotated[RegistryKey[WorldPurposePackRegistry], BeforeValidator(_wire_pack_id)]
    ]
    allowed: DefaultWhenMissing[
        Annotated[list[AllowedToken], BeforeValidator(_wire_pack_allowed)]
    ] = Field(default_factory=list)
