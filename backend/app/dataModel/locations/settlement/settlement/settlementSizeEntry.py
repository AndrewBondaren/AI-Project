"""One `worlds.settlement_size_registry[]` row — relative rank only (LOC-T-2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.registryKey import RegistryKey

if TYPE_CHECKING:
    from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import (
        WorldSettlementSizeRegistry,
    )


class SettlementSizeEntry(BaseModel):
    """Identity + display. Rank key is ``RegistryKey[WorldSettlementSizeRegistry]``."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_size: StrictOnWire[RegistryKey[WorldSettlementSizeRegistry]]
    display_size: DefaultOnWire[str | None] = None
