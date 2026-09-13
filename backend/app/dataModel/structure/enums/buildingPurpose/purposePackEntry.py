"""One ``worlds.purpose_pack_registry[]`` row — tz_building_generator.md §2.1."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.registryKey import RegistryKey
from app.dataModel.structure.enums.buildingPurpose.catalog import (
    AllowedToken,
    coerce_allowed_list,
)
from app.dataModel.structure.enums.buildingPurpose.packs import normalize_pack_id

if TYPE_CHECKING:
    from app.dataModel.structure.enums.buildingPurpose.worldPurposePackRegistry import (
        WorldPurposePackRegistry,
    )

logger = logging.getLogger(__name__)


def _wire_pack_id(value: Any) -> Any:
    token = normalize_pack_id(value)
    return token if token is not None else value


def _wire_pack_allowed(value: Any) -> list[AllowedToken]:
    if value is None:
        return []
    items: list[object]
    if isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [value]
    coerced = coerce_allowed_list(items)
    kept = {str(token) for token in coerced}
    for item in items:
        token = normalize_pack_id(item)
        if token and token not in kept:
            logger.warning(
                "Unknown purpose token %r in pack allowed — dropped "
                "(not inventing a leaf)",
                item,
            )
    return coerced


class PurposePackEntry(BaseModel):
    """Pack recipe: which known families/leaves this mask turns on."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_pack: StrictOnWire[
        Annotated[RegistryKey[WorldPurposePackRegistry], BeforeValidator(_wire_pack_id)]
    ]
    allowed: DefaultOnWire[
        Annotated[list[AllowedToken], BeforeValidator(_wire_pack_allowed)]
    ] = Field(default_factory=list)
