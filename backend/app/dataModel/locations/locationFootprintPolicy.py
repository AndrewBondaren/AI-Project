"""Footprint pipeline selection by payload contract — tz_locations §Payload per type."""

from app.dataModel.locations.locationType.worldLocationTypeRegistry import WorldLocationTypeRegistry
from app.dataModel.locations.payloadKind import PayloadKind


def _payload_kind(system_type: str | None, registry: WorldLocationTypeRegistry | None):
    resolved = registry if registry is not None else WorldLocationTypeRegistry.canonical_engine()
    entry = resolved.entry_for((system_type or "").strip().lower())
    return entry.payload_kind if entry is not None else None


def uses_settlement_fine_footprint(
    *, system_location_type: str | None,
    system_location_subtype: str | None = None,
    registry: WorldLocationTypeRegistry | None = None,
) -> bool:
    """Settlement roots and district payloads use the assembler fine grid."""
    return _payload_kind(system_location_type, registry) in (
        PayloadKind.SETTLEMENT, PayloadKind.DISTRICT,
    )


def named_location_uses_settlement_fine_footprint(
    location: object, *, registry: WorldLocationTypeRegistry | None = None,
) -> bool:
    return uses_settlement_fine_footprint(
        system_location_type=getattr(location, "system_location_type", None),
        registry=registry,
    )


def is_settlement_map_site(
    *, system_location_type: str | None,
    system_location_subtype: str | None = None,
    registry: WorldLocationTypeRegistry | None = None,
) -> bool:
    """A settlement payload selects the root pipeline, regardless of type name."""
    return _payload_kind(system_location_type, registry) is PayloadKind.SETTLEMENT


def named_location_is_settlement_map_site(
    location: object, *, registry: WorldLocationTypeRegistry | None = None,
) -> bool:
    return is_settlement_map_site(
        system_location_type=getattr(location, "system_location_type", None),
        registry=registry,
    )
