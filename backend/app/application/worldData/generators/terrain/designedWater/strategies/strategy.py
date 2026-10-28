"""Pure strategy preparation contract; failures use existing PlanBuildFailure."""

from typing import Protocol

from app.dataModel.terrain.designedWater.draft import WaterDesignDraft
from app.dataModel.terrain.designedWater.input import WaterDesignInput


class DesignedWaterStrategy(Protocol):
    def design(self, input: WaterDesignInput) -> WaterDesignDraft: ...
