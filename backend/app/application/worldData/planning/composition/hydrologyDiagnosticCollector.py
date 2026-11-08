from collections.abc import Callable

from app.dataModel.hydrology import waterDiagnostics as water
from app.dataModel.hydrology.riverRouting import RiverPlanDiagnostic


HydrologyDiagnostic = (
    water.WaterPuddleDiagnostic | water.WaterCannotHoldDiagnostic | water.WaterTerrainUnresolvedDiagnostic
    | water.WaterNoOceanDepressionDiagnostic | water.WaterLevelSpillDiagnostic
    | water.WaterLevelSupersededDiagnostic | water.WaterWorldOceanDiagnostic | RiverPlanDiagnostic
)
type HydrologyCallback = Callable[[HydrologyDiagnostic], None]


class HydrologyDiagnosticCollector:
    def __init__(self) -> None:
        self._facts: dict[HydrologyDiagnostic, None] = {}

    def collect(self, diagnostic: HydrologyDiagnostic) -> None:
        self._facts[diagnostic] = None

    @property
    def facts(self) -> tuple[HydrologyDiagnostic, ...]:
        return tuple(self._facts)
