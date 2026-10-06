"""Authored and type-stamped settlement data — tz_locations §Payload per type."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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
    """Shared field definitions while the legacy skeleton is being migrated."""
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


class SettlementPayload(SettlementPayloadFields):
    is_inhabited: DefaultOnWire[bool] = True
