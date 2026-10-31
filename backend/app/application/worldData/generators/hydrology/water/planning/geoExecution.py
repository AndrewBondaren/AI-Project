"""Shared GEO physical execution settings from terminal category decisions."""
from pydantic import TypeAdapter
from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


_DECISIONS = TypeAdapter[tuple[tuple[Category, HydrologyGenerationDecision], ...]](
    tuple[tuple[Category, HydrologyGenerationDecision], ...])


def geo_execution_decisions(classification_decisions: tuple[tuple[Category, HydrologyGenerationDecision], ...]) -> tuple[tuple[Category, HydrologyGenerationDecision], ...]:
    try:
        decisions = _DECISIONS.validate_python(classification_decisions, strict=True)
        if tuple(category for category, _ in decisions) != tuple(sorted(Category, key=lambda c: c.value)):
            raise ValueError("GEO fill requires one canonical decision for every water category")
        modes = {}
        for category, decision in decisions:
            mode = decision.require_behavior()
            if ((mode is Mode.DISABLED and decision.state is not PolicyState.DISABLED)
                    or (mode is not Mode.DISABLED and decision.state is not PolicyState.READY)):
                raise ValueError("GEO fill requires terminal generation decisions")
            modes[category] = mode
    except ValueError as error:
        raise PlanBuildFailure((FieldPathError(("classification_decisions",), str(error)),)) from error
    return decisions


def geo_execution_modes(classification_decisions: tuple[tuple[Category, HydrologyGenerationDecision], ...]) -> dict[Category, Mode]:
    return {category: decision.require_behavior() for category, decision in geo_execution_decisions(classification_decisions)}


def geo_auto_lakes(inputs: GeoHydrologyPlanInput, modes: dict[Category, Mode]) -> bool:
    return modes[Category.LAKE] is Mode.AUTORESOLVE and BasinKind.LAKE in inputs.allowed_body_kinds
