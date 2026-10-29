"""Ready plate inputs; zero quota lets field tests include tiny worlds."""
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.geo1.preparation.fixtures import procedural_case


def case(*,mode=Mode.PLANAR,policy=None,span=2,bounds=None):
    input,_=procedural_case(strategy=Strategy.PLATE,mode=mode,span=span,allocated=0,
        bounds=bounds or WorldBounds(x_min=-2,x_max=3,y_min=-1,y_max=2))
    if policy is not None:
        input=type(input).model_validate(input.model_copy(update={"field_policy":input.field_policy.model_copy(update={"plate_policy":policy})}))
    return input
