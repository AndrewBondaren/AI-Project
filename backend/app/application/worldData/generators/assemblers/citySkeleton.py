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
from app.dataModel.settlement.settlement.worldLocationMoodRegistry import LocationMoodKey
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


def _copy_pojo_value(value: object) -> object:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def _branded_resolved_aliases(*, economic_tier: str | None) -> dict[str, EconomyTierKey | None]:
    """Aliased skeleton fields come from generate resolve, not the NL column copy."""
    supplied = {"economic_tier": economic_tier}
    expected = set(SettlementSkeleton.NAMED_LOCATION_FIELD_ALIASES)
    extra = set(supplied) - expected
    missing = expected - set(supplied)
    if extra or missing:
        raise RuntimeError(
            "city_skeleton_from_settlement resolved kwargs must match "
            "SettlementSkeleton.NAMED_LOCATION_FIELD_ALIASES "
            f"(missing={sorted(missing)} extra={sorted(extra)})"
        )
    branded: dict[str, EconomyTierKey | None] = {}
    for name, raw in supplied.items():
        branded[name] = (
            getattr(SettlementSkeleton.model_validate({name: raw}), name)
            if raw
            else None
        )
    return branded


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
        if name == "dominant_material":
            payload[name] = None
            continue
        payload[name] = _copy_pojo_value(getattr(pojo, name))
    payload.update(_branded_resolved_aliases(economic_tier=economic_tier))
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
    system_location_mood: LocationMoodKey | None
    frontage_type_order:  list[ConnectionTypeKey] | None = None
    plot_counts:          dict[DrawingKey, int] | None = None
    plot_priority:        dict[DrawingKey, int] | None = None
    perimeter_barrier:    PerimeterBarrier | None = None
    typical_districts:    list[TypicalDistrictRef] | None = None
    system_settlement_specializations: list[SettlementSpecializationBind] | None = None
