"""Terminal location cascade values — tz_cascade_context §3–§4."""

from pydantic import BaseModel, ConfigDict, computed_field

from app.dataModel.cascade.cascadeSpec import DefaultPolicy
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import (
    EconomyTierKey, WorldEconomyTierRegistry,
)
from app.dataModel.locations.settlement.enums.districtDensity import DistrictDensity
from app.dataModel.locations.settlement.settlement.worldSettlementSizeRegistry import (
    SettlementSizeKey, WorldSettlementSizeRegistry,
)
from app.dataModel.materials import CONSTRUCTION_MATERIAL_DEFAULTS
from app.dataModel.materials.worldMaterialRegistry import MaterialKey


class LocationCascadeDefaults(BaseModel):
    """Defaults belong to this POJO; nullable authored nodes inherit.

    The caller supplies the resolved world registry. Its median is read
    only when the cascade reaches the economic-tier fallback, never at
    root construction or when an authored channel wins.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    tier_registry: WorldEconomyTierRegistry
    system_city_size: SettlementSizeKey = WorldSettlementSizeRegistry.default_system_size()
    settlement_density: DistrictDensity = DistrictDensity.default()
    wall_material: MaterialKey = CONSTRUCTION_MATERIAL_DEFAULTS.wall
    floor_material: MaterialKey = CONSTRUCTION_MATERIAL_DEFAULTS.floor
    dominant_material: MaterialKey = CONSTRUCTION_MATERIAL_DEFAULTS.dominant

    @computed_field
    @property
    def economic_tier(self) -> EconomyTierKey:
        return self.tier_registry.resolve_default(DefaultPolicy.REGISTRY_MEDIAN)
