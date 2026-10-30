"""One ready water design operation; no dependency scheduling or batch lifecycle."""

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.designedWater.preparation.designUniverse import WaterDesignUniverse
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.terrain.designedWater.coverage.budget import WaterCoverageBudget
from app.dataModel.terrain.designedWater.input import WaterStrategyInput
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation


class ReadyWaterDesignJob:
    def __init__(self, universe: WaterDesignUniverse, strategies: DesignedWaterStrategyFactory,
                 control: PlanBuildControl) -> None:
        self.universe, self.strategies, self.control = universe, strategies, control
        self.preparer = DesignedWaterPlacementPreparer()

    def prepare(self, admission: PlacementAdmissionInput, value: WaterStrategyInput,
                budget: WaterCoverageBudget | None) -> tuple[WaterDesignPreparation, PreparedPlacementV2]:
        value = self.universe.require_input(admission, value, budget)
        self.control.raise_if_shutdown()
        draft = self.strategies.get(value.strategy).design(value)
        self.control.raise_if_shutdown()
        design = self.preparer.prepare(value, draft, selection_policy=self.universe.selection_policy)
        prepared = self.preparer.bind_admission(value, design,
            intent=self.universe.by_region[admission.header.identity.region_uid], admission=admission)
        return design, prepared
