"""Ready world-fine noise inputs, independent of generated relief."""
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.geo1.preparation.fixtures import procedural_case


def case(*,mode=Mode.PLANAR,policy=None,span=2,bounds=None):
    input,_=procedural_case(mode=mode,span=span,allocated=0,bounds=bounds or WorldBounds(x_min=-2,x_max=3,y_min=-1,y_max=2))
    if policy is not None:
        input=type(input).model_validate(input.model_copy(update={"field_policy":input.field_policy.model_copy(update={"noise_policy":policy})}))
    return input
