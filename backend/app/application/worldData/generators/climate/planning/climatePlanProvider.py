"""Base pole layout and local climate dependency boundary; no live reads or private cache."""


from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.climatePoints import ClimatePolePoint
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput, ClimateBaseIssueCode
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.climate.planning.climatePlan import ClimateLocalPlan
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.application.worldData.generators.climate.planning.basePoleLayout import autoresolve_base_poles, manual_base_pole
from app.application.worldData.generators.climate.localFieldFromCoarse import build_local_plan_from_coarse


def build_climate_base(inputs: ClimateBaseInput) -> PlanBuildResult[ClimateBasePlan]:
    diagnostics: list[PlanDiagnostic] = []

    def issue(code: ClimateBaseIssueCode, message: str) -> None:
        diagnostics.append(PlanDiagnostic(issue=inputs.diagnostic_issue(code, message),
            disposition=PlanDiagnosticDisposition.FALLBACK))

    poles: tuple[ClimatePolePoint, ...] = ()
    if inputs.manual_poles:
        if len(inputs.manual_poles) > 1:
            issue(ClimateBaseIssueCode.MULTIPLE_POLES,
                  f"declared {len(inputs.manual_poles)} poles; using first only")
        manual = next(iter(inputs.manual_poles))
        if manual.zone is None:
            issue(ClimateBaseIssueCode.POLE_NO_ZONE,
                  f"pole={manual.location_uid} has no system_climate_zone; ignored")
        else:
            point = manual_base_pole(manual, inputs.fine_span, inputs.peak_min, inputs.peak_max)
            if point is not None:
                poles = (point,)
    if not poles:
        if inputs.mode == ClimatePoleMode.AUTORESOLVE:
            # The legacy no-extent bootstrap bbox is retained; it is not a world extent.
            poles = autoresolve_base_poles(inputs.seed, inputs.preset, inputs.peak_min, inputs.peak_max,
                                           inputs.bbox if inputs.bbox is not None else GridBBox(0, 1, 0, 1))
        else:
            issue(ClimateBaseIssueCode.MANUAL_MODE_NO_POLE, "mode=manual with no climate_pole; empty pole field")
    plan = ClimateBasePlan(poles=poles, bbox=inputs.bbox, default_zone=inputs.default_zone,
                           profiles=inputs.profiles, blend=inputs.blend)
    return PlanBuildResult[ClimateBasePlan](payload=plan, diagnostics=tuple(diagnostics))


class ClimateBasePlanProvider:
    def build(self, request: PlanRequest[ClimateBaseInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[ClimateBasePlan]:
        control.raise_if_shutdown()
        if request.dependencies:
            raise ValueError("base climate has no dependencies")
        result = build_climate_base(request.inputs)
        control.raise_if_shutdown()
        return result


class ClimateLocalPlanProvider:
    def __init__(self, climate_base: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan],
                 hydrology: RegisteredPlanContract[HydrologyFinalInput, HydrologyPlan]) -> None:
        self._base, self._hydrology = climate_base, hydrology

    def build(self, request: PlanRequest[ClimateLocalInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[ClimateLocalPlan]:
        control.raise_if_shutdown()
        base_slot, hydro_slot = PlanSlot(SurfacePlanSlot.CLIMATE_BASE.value), PlanSlot(SurfacePlanSlot.HYDROLOGY.value)
        base = dependencies.require(base_slot, self._base)
        hydrology = dependencies.require(hydro_slot, self._hydrology)
        refs = {dependency.slot: dependency.ref for dependency in request.dependencies}
        if refs != {base_slot: base.ref, hydro_slot: hydrology.ref}:
            raise PlanBuildFailure((FieldPathError(("dependencies",), "local climate requires exact upstream refs"),))
        result = build_local_plan_from_coarse(request.inputs, base.payload, hydrology.payload)
        control.raise_if_shutdown()
        return result

