from dataclasses import dataclass, fields as dataclass_fields

from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.dataModel.settlement.settlement.settlementSpecializationBind import (
    SettlementSpecializationBind,
)
from app.dataModel.settlement.settlement.typicalDistrictRef import TypicalDistrictRef
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
            payload[name] = economic_tier
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
    economic_tier:        str | None   # ref → worlds.economic_tier_registry
    architectural_style:  str | None   # ref → worlds.architectural_style_registry
    dominant_material:    str | None   # ref → worlds.material_registry
    settlement_density:   str | None   # DistrictDensity wire
    system_city_size:     str | None   # ref → worlds.city_size_registry
    system_location_mood: str | None   # ref → worlds.location_mood_registry
    frontage_type_order:  list[str] | None = None
    structure_counts:     dict[str, int] | None = None
    structure_priority:   dict[str, int] | None = None
    perimeter_barrier:    PerimeterBarrier | None = None
    typical_districts:    list[TypicalDistrictRef] | None = None
    system_settlement_specializations: list[SettlementSpecializationBind] | None = None
