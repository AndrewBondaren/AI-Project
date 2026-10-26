from app.dataModel.climate.planning.climatePoints import ClimatePolePoint as ClimatePolePoint


from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND, ClimatePoleBlendDefaults
from app.dataModel.climate.climatePoleTemperature import (
    POLE_TEMPERATURE_INSET_FRACTION,
    derived_pole_temperature,
)
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.enums.poleSource import PoleSource

POLE_BLEND_EPS = CLIMATE_POLE_BLEND.eps
POLE_BLEND_POWER = CLIMATE_POLE_BLEND.power
