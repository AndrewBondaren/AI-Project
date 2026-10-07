"""Assemble source/resolved skeleton POJOs — tz_locations §Payload per type."""

from app.application.worldData.locationPayloadAccess import settlement_payload
from app.dataModel.locations.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.db.models.namedLocation import NamedLocation


def settlement_skeleton_pojo(settlement: NamedLocation) -> SettlementSkeleton:
    """Authored source view; generic stamps are mapped at the caller boundary."""
    return SettlementSkeleton.model_validate({
        **settlement_payload(settlement).model_dump(),
        "economic_tier": settlement.system_economic_tier,
        "system_location_mood": settlement.system_location_mood,
    })


def resolved_settlement_skeleton(
    settlement: NamedLocation,
    *,
    economic_tier: str | None,
    settlement_density: DistrictDensity | str | None,
) -> SettlementSkeleton:
    """Assembler view with resolved tier/density; material comes from cascade/fold."""
    return SettlementSkeleton.model_validate({
        **settlement_skeleton_pojo(settlement).model_dump(),
        "economic_tier": economic_tier or None,
        "settlement_density": settlement_density,
        "dominant_material": None,
    })
