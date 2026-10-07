"""Authored and type-stamped settlement data — tz_locations §Payload per type."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from typing import Annotated, Self
from app.dataModel.cascade.cascadeSpec import CascadeChannel, CascadeLink, FieldRef
from app.dataModel.locations.context.cascadeParams import CITY_SIZE, SETTLEMENT_DENSITY, DOMINANT_MATERIAL
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.settlement.district.districtTemplateEntry import DistrictTemplateEntry

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.connections.connectionType.worldConnectionTypeRegistry import ConnectionTypeKey
from app.dataModel.locations.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.locations.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.locations.settlement.settlement.settlementSpecializationBind import SettlementSpecializationBind
from app.dataModel.locations.settlement.settlement.typicalDistrictRef import TypicalDistrictRef
from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import SettlementSizeKey
from app.dataModel.locations.structure.building.plotLayoutTemplate import DrawingKey
from app.dataModel.materials.worldMaterialRegistry import MaterialKey


class SettlementPayloadFields(BaseModel):
    """Shared authored field definitions for payload storage and assembler POJO."""
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_city_size: DefaultOnWire[SettlementSizeKey | None] = None
    settlement_density: DefaultOnWire[DistrictDensity | None] = None
    dominant_material: DefaultOnWire[MaterialKey | None] = None
    architectural_style: DefaultOnWire[str | None] = None
    frontage_type_order: DefaultOnWire[list[ConnectionTypeKey] | None] = None
    plot_counts: DefaultOnWire[dict[DrawingKey, int] | None] = Field(
        default=None, validation_alias=AliasChoices("plot_counts", "structure_counts"),
    )
    plot_priority: DefaultOnWire[dict[DrawingKey, int] | None] = Field(
        default=None, validation_alias=AliasChoices("plot_priority", "structure_priority"),
    )
    perimeter_barrier: DefaultOnWire[PerimeterBarrier | None] = None
    typical_districts: DefaultOnWire[list[TypicalDistrictRef] | None] = None
    system_settlement_specializations: DefaultOnWire[list[SettlementSpecializationBind] | None] = None
    # Economic gate flag. Economic filters are NOT wired to it yet;
    # recheck current wiring before implementing that gate.
    is_inhabited: DefaultOnWire[bool] = False


# Selectors live outside Annotated so static checkers inspect attributes.
_DISTRICT_TEMPLATE_ENTRY_DENSITY = FieldRef(lambda: DistrictTemplateEntry, lambda pojo: pojo.density)


class SettlementPayload(SettlementPayloadFields):
    system_city_size: Annotated[
        DefaultOnWire[SettlementSizeKey | None],
        CascadeChannel(CITY_SIZE, ScopeLevel.SETTLEMENT),
    ] = None
    settlement_density: Annotated[
        DefaultOnWire[DistrictDensity | None],
        CascadeChannel(SETTLEMENT_DENSITY, ScopeLevel.SETTLEMENT,
                       above=CascadeLink(_DISTRICT_TEMPLATE_ENTRY_DENSITY, ScopeLevel.DISTRICT)),
    ] = None
    dominant_material: Annotated[
        DefaultOnWire[MaterialKey | None],
        CascadeChannel(DOMINANT_MATERIAL, ScopeLevel.SETTLEMENT),
    ] = None

    @model_validator(mode="after")
    def validate_inhabited_specializations(self) -> Self:
        if not self.is_inhabited and self.system_settlement_specializations:
            raise ValueError("system_settlement_specializations requires is_inhabited=true")
        return self
