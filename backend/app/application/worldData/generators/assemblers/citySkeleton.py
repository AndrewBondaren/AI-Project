from dataclasses import dataclass

from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.db.models.namedLocation import NamedLocation


def _skeleton_wire_from_location(settlement: NamedLocation) -> dict:
    payload: dict = {}
    for name in SettlementSkeleton.model_fields:
        value = getattr(settlement, name, None)
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
    frontage = (
        list(pojo.frontage_type_order)
        if pojo.frontage_type_order is not None
        else None
    )
    counts = dict(pojo.structure_counts) if pojo.structure_counts is not None else None
    priority = (
        dict(pojo.structure_priority)
        if pojo.structure_priority is not None
        else None
    )
    return CitySkeleton(
        economic_tier=economic_tier,
        architectural_style=pojo.architectural_style,
        dominant_material=None,
        settlement_density=pojo.settlement_density,
        system_city_size=settlement.system_city_size or pojo.system_city_size,
        system_location_mood=settlement.system_location_mood or pojo.system_location_mood,
        frontage_type_order=frontage,
        structure_counts=counts,
        structure_priority=priority,
        perimeter_barrier=pojo.perimeter_barrier,
    )


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
    settlement_density:   str | None   # "sparse" | "medium" | "dense"
    system_city_size:     str | None   # ref → worlds.city_size_registry
    system_location_mood: str | None   # ref → worlds.location_mood_registry
    frontage_type_order:  list[str] | None = None
    structure_counts:     dict[str, int] | None = None
    structure_priority:   dict[str, int] | None = None
    perimeter_barrier:    PerimeterBarrier | None = None
