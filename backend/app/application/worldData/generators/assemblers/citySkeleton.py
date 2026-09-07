from dataclasses import dataclass, fields as dataclass_fields

from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import (
    ConnectionTypeKey,
)
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.dataModel.settlement.settlement.settlementSpecializationBind import (
    SettlementSpecializationBind,
)
from app.dataModel.settlement.settlement.typicalDistrictRef import TypicalDistrictRef
from app.dataModel.settlement.settlement.worldSettlementSizeRegistry import SettlementSizeKey
from app.dataModel.structure.building.buildingLayoutTemplate import DrawingKey
from app.db.models.namedLocation import NamedLocation


def _nl_attr_for_skeleton_field(name: str) -> str:
    return SettlementSkeleton.NAMED_LOCATION_FIELD_ALIASES.get(name, name)


def _skeleton_wire_from_location(settlement: NamedLocation) -> dict:
    payload: dict = {}
    for name in SettlementSkeleton.model_fields:
        attr = _nl_attr_for_skeleton_field(name)
        value = getattr(settlement, attr)
        if value is not None:
            payload[name] = value
    return payload


def city_skeleton_from_settlement(
    settlement: NamedLocation,
    *,
    economic_tier: str | None,
) -> "CitySkeleton":
    """Mirror SettlementSkeleton onto runtime CitySkeleton (assembler §7.1)."""
    pojo = SettlementSkeleton.model_validate(_skeleton_wire_from_location(settlement))
    payload: dict = {}
    for field in dataclass_fields(CitySkeleton):
        name = field.name
        if name == "economic_tier":
            payload[name] = (
                SettlementSkeleton.model_validate(
                    {"economic_tier": economic_tier},
                ).economic_tier
                if economic_tier
                else None
            )
            continue
        if name == "dominant_material":
            payload[name] = None
            continue
        value = getattr(pojo, name)
        if isinstance(value, list):
            value = list(value)
        elif isinstance(value, dict):
            value = dict(value)
        payload[name] = value
    if settlement.system_city_size:
        payload["system_city_size"] = settlement.system_city_size
    if settlement.system_location_mood:
        payload["system_location_mood"] = settlement.system_location_mood
    return CitySkeleton(**payload)


@dataclass
class CitySkeleton:
    """
    Поля скелета поселения. Создаётся SettlementAssembler из NamedLocation поселения
    и передаётся вниз по иерархии без изменений.

    Все поля nullable — поселение может существовать без части атрибутов.
    C22-поля — зеркало SettlementSkeleton (wire); сбор — city_skeleton_from_settlement.
    """
    economic_tier:        EconomyTierKey | None
    architectural_style:  str | None   # ref → worlds.architectural_style_registry
    dominant_material:    MaterialKey | None
    settlement_density:   DistrictDensity | None
    system_city_size:     SettlementSizeKey | None
    system_location_mood: str | None   # ref → worlds.location_mood_registry
    frontage_type_order:  list[ConnectionTypeKey] | None = None
    plot_counts:          dict[DrawingKey, int] | None = None
    plot_priority:        dict[DrawingKey, int] | None = None
    perimeter_barrier:    PerimeterBarrier | None = None
    typical_districts:    list[TypicalDistrictRef] | None = None
    system_settlement_specializations: list[SettlementSpecializationBind] | None = None
