"""Stable surface TLV registrations for app.dataModel.economy."""

from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import WorldEconomyTierRegistry
from app.dataModel.encoding.schemaManifest import CanonicalTypeKind


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (45, WorldEconomyTierRegistry, CanonicalTypeKind.RECORD),
    (46, EconomyTierEntry, CanonicalTypeKind.RECORD),
)
