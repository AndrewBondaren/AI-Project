"""Bind already computed authored geometry; its producer remains the water adapter."""

from pydantic import TypeAdapter

from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision, WaterDesignDecision
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, AuthoredLakeSource
from app.dataModel.placement.common import PlacementMode
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput, WaterDesignInput
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

_GENERATION = TypeAdapter(HydrologyGenerationDecision)
_ADMISSION = TypeAdapter(WaterDesignDecision)


class AuthoredWaterSourceAdapter:
    def prepare_source(
        self, input: WaterDesignInput[AuthoredBasinSource | AuthoredLakeSource], *,
        generation: HydrologyGenerationDecision, admission: PlacementAdmissionInput,
        geometry: AuthoredWaterGeometry,
    ) -> AuthoredWaterDesignInput[AuthoredBasinSource | AuthoredLakeSource]:
        try:
            shared = WaterDesignInput[AuthoredBasinSource | AuthoredLakeSource].model_validate(input, strict=True)
            generation = _GENERATION.validate_python(generation, strict=True)
            admission = PlacementAdmissionInput.model_validate(admission, strict=True)
            decision = _ADMISSION.validate_python(admission.decision, strict=True)
            if generation.state is not PolicyState.READY or decision.state is not PolicyState.READY:
                raise ValueError("authored input requires ready generation and admission")
            mode = generation.require_behavior()
            if mode not in (Mode.DECLARED_ONLY, Mode.AUTORESOLVE) or (
                    (mode is Mode.AUTORESOLVE) is not shared.context.autoresolve):
                raise ValueError("authored generation must match the resolved active context")
            if shared.strategy is not Strategy.AUTHORED_REGION or decision.require_behavior() is not shared.strategy:
                raise ValueError("authored admission must retain the resolved AUTHORED_REGION strategy")
            identity = admission.header.identity
            if (identity.source_uid != shared.source.value.location_uid
                    or identity.world_uid != shared.pre_hydrology.ref.key.world_uid
                    or admission.header.mode is not PlacementMode.ABSOLUTE):
                raise ValueError("authored admission must match the captured source/world and absolute geometry")
            if any(d.target_uid in (identity.source_uid, identity.region_uid) for d in admission.header.dependencies):
                raise ValueError("authored source cannot depend on itself or its future water")
            values = {name: getattr(shared, name) for name in WaterDesignInput.model_fields}
            values["geometry"] = geometry
            return AuthoredWaterDesignInput[AuthoredBasinSource | AuthoredLakeSource].model_validate(values, strict=True)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("water_source",), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error
