"""Join captured inputs for one coastline source; decisions remain common policy."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.preparation.coastlineConstraintPreparer import CoastlineConstraintPreparer
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision, WaterPolicyReason
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource, WaterDesignSourceKind
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.placement.common import PlacementMode
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, ValueSelectionDecision
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe, WaterFieldRecipe
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometryRequest, LegacyAuthoredWaterGeometryRequest
from app.dataModel.terrain.designedWater.input import (
    AuthoredWaterDesignInput, CoastlineWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput,
    NativeCoastlineStrategyContext, NativeCoastlineStrategyInput, PlateNoiseWaterDesignInput, WaterDesignInput,
)
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.terrain.designedWater.waterDesignTypeError import WaterDesignTypeError

_RECIPE = TypeAdapter(WaterFieldRecipe)
_GENERATION = TypeAdapter(HydrologyGenerationDecision)


@contextmanager
def _validation_path(uid: str, model: type[BaseModel], *path: str) -> Iterator[None]:
    try:
        yield
    except ValidationError as error:
        raise PlanBuildFailure(tuple(
            WaterDesignTypeError.at(model, detail["loc"], detail["msg"], operation="water_source",
                                    source_uid=uid, prefix=path)
            for detail in error.errors(include_input=False, include_context=False, include_url=False)
        )) from error


def _ready_mode(source: DeclaredCoastline, request: AuthoredWaterGeometryRequest | LegacyAuthoredWaterGeometryRequest,
                context: ResolvedWaterGenerationContext, admission: PlacementAdmissionInput,
                generation: HydrologyGenerationDecision, metadata: WaterSourceMetadata) -> HydrologyExecutionMode:
    uid = source.location_uid
    with _validation_path(uid, ResolvedWaterGenerationContext, "context"):
        context = ResolvedWaterGenerationContext.model_validate(context, strict=True)
    with _validation_path(uid, PlacementAdmissionInput, "admission"):
        admission = PlacementAdmissionInput.model_validate(admission, strict=True)
    with _validation_path(uid, type(admission.decision), "admission", "decision"):
        decision = ObjectAdmissionDecision[Strategy, WaterPolicyReason].model_validate(admission.decision, strict=True)
    with _validation_path(uid, type(generation), "generation"):
        generation = _GENERATION.validate_python(generation, strict=True)
    errors = ValidatorAggregationHelper((WaterDesignTypeError,))

    def report[M: BaseModel, T](model: M, select: Callable[[M], T], message: str, *parent: str) -> None:
        field = bind_field(FieldRef(lambda: type(model), select)).field
        if parent[0] == "admission":
            root, loc, prefix = PlacementAdmissionInput, (*parent[1:], field), ("admission",)
        else:
            root, loc, prefix = type(model), (field,), parent
        errors.add(WaterDesignTypeError.at(root, loc, message, operation="water_source", source_uid=uid, prefix=prefix))

    if decision.state is not PolicyState.READY:
        report(decision, lambda d: d.state, "coastline requires ready admission", "admission", "decision")
    elif decision.behavior is not context.strategy:
        report(decision, lambda d: d.behavior, "admission strategy must match the resolved context", "admission", "decision")
    if generation.state is not PolicyState.READY:
        report(generation, lambda g: g.state, "coastline requires ready generation", "generation")
    else:
        mode = generation.require_behavior()
        if mode not in (HydrologyExecutionMode.DECLARED_ONLY, HydrologyExecutionMode.AUTORESOLVE):
            report(generation, lambda g: g.behavior, "ready generation requires DECLARED_ONLY or AUTORESOLVE", "generation")
        elif (mode is HydrologyExecutionMode.AUTORESOLVE) is not context.autoresolve:
            report(context, lambda c: c.autoresolve, "generation decision must match resolved context autoresolve", "context")
    if request.source != CoastlineWaterSource(value=source):
        report(request, lambda r: r.source, "geometry request must capture the same complete coastline source", "geometry_request")
    identity = admission.header.identity
    if identity.source_uid != uid:
        report(identity, lambda i: i.source_uid, "admission source UID must match the coastline", "admission", "header", "identity")
    if identity.world_uid != request.pre_hydrology.ref.key.world_uid:
        report(identity, lambda i: i.world_uid, "admission world must match the captured terrain", "admission", "header", "identity")
    if admission.header.mode is not PlacementMode.ABSOLUTE:
        report(admission.header, lambda h: h.mode, "authored coastline path requires absolute placement", "admission", "header")
    if any(d.target_uid in (identity.source_uid, identity.region_uid) for d in admission.header.dependencies):
        report(admission.header, lambda h: h.dependencies, "water source cannot depend on itself or its future water", "admission", "header")
    # The native context owns this check alongside its other cross-field invariants.
    if isinstance(request, LegacyAuthoredWaterGeometryRequest) and metadata.source_kind is not WaterDesignSourceKind.COASTLINE:
        report(metadata, lambda m: m.source_kind, "coastline metadata must retain the source origin", "metadata")
    errors.raise_if_any(PlanBuildFailure)
    return generation.require_behavior()


class CoastlineWaterSourceAdapter:
    """Validate the ready join, delegate geometry, bind the existing strategy input.

    The caller owns captured inputs and early lifecycle admission. This adapter
    neither executes policy/strategy nor allocates coverage or writes terrain.
    """

    def prepare_native(self, source: DeclaredCoastline, *, geometry_request: AuthoredWaterGeometryRequest,
            expected_window: PlanRef, context: ResolvedWaterGenerationContext, generation: HydrologyGenerationDecision,
            region: TerrainRegionExtent, budget: BodyCoverageAllocation, region_coverage: RegionCoverage,
            metadata: WaterSourceMetadata, admission: PlacementAdmissionInput,
            field_policy: WaterFieldRecipe) -> NativeCoastlineStrategyInput:
        if not isinstance(source, DeclaredCoastline) or not isinstance(geometry_request, AuthoredWaterGeometryRequest):
            raise TypeError("native coastline join requires a typed source and fine geometry request")
        uid = source.location_uid
        errors = ValidatorAggregationHelper((WaterDesignTypeError,))
        with _validation_path(uid, AuthoredWaterGeometryRequest, "geometry_request"):
            request = AuthoredWaterGeometryRequest.model_validate(geometry_request, strict=True)
        try:
            expected_window = PlanRef.model_validate(expected_window, strict=True)
        except ValidationError as error:
            for detail in error.errors(include_input=False, include_url=False):
                errors.add(WaterDesignTypeError.at(PlanRef, detail["loc"], detail["msg"], operation="water_source",
                                                   source_uid=uid, prefix=("expected_window",)))
        else:
            if request.pre_hydrology.ref != expected_window:
                errors.add(WaterDesignTypeError.at(type(request), ("pre_hydrology", "ref"),
                    "coastline request must match the expected fine window revision", operation="water_source",
                    source_uid=uid, prefix=("geometry_request",), expected_window=expected_window))

        with _validation_path(uid, CoastlineWaterSource, "source"):
            wrapped = CoastlineWaterSource(value=source)
        try:
            mode = _ready_mode(source, request, context, admission, generation, metadata)
            if mode is not HydrologyExecutionMode.AUTORESOLVE:
                errors.add(WaterDesignTypeError.at(type(generation), ("behavior",),
                    "native coastline requires ready AUTORESOLVE before preparation", operation="water_source", source_uid=uid, prefix=("generation",)))
        except PlanBuildFailure as failure:
            if failure.diagnostics:
                raise
            for issue in failure.issues:
                if not isinstance(issue, WaterDesignTypeError):
                    raise
                errors.add(issue)

        try:
            captured = NativeCoastlineStrategyContext(strategy=context.strategy, source=wrapped, metadata=metadata,
                context=context, region=region, budget=budget, seed_root=request.seed_root, topology=request.topology,
                grid=request.grid, pre_hydrology=request.pre_hydrology, region_coverage=region_coverage,
                field_policy=field_policy, z_min=request.z_min)
        except ValidationError as error:
            for detail in error.errors(include_input=False, include_url=False):
                errors.add(WaterDesignTypeError.at(NativeCoastlineStrategyContext, detail["loc"], detail["msg"],
                                                   operation="water_source", source_uid=uid))
            errors.raise_if_any(PlanBuildFailure)
            raise

        errors.raise_if_any(PlanBuildFailure)
        with _validation_path(uid, NativeCoastlineStrategyInput):
            constraints = CoastlineConstraintPreparer().prepare_native(request)
            return NativeCoastlineStrategyInput.model_validate(dict(captured, constraints=constraints), strict=True)

    # GEO-LEGACY-22: Replace the legacy coastline request.
    def prepare_source(
        self, source: DeclaredCoastline, *, geometry_request: LegacyAuthoredWaterGeometryRequest,
        context: ResolvedWaterGenerationContext, generation: HydrologyGenerationDecision,
        region: TerrainRegionExtent, budget: BodyCoverageAllocation, region_coverage: RegionCoverage,
        metadata: WaterSourceMetadata, admission: PlacementAdmissionInput, field_policy: WaterFieldRecipe | None,
    ) -> CoastlineWaterDesignInput:
        if not isinstance(source, DeclaredCoastline) or not isinstance(geometry_request, LegacyAuthoredWaterGeometryRequest):
            raise TypeError("coastline source join requires typed source and geometry request")
        if not isinstance(context, ResolvedWaterGenerationContext) or not isinstance(admission, PlacementAdmissionInput):
            raise TypeError("coastline source join requires resolved context and admission")
        if not isinstance(generation, ValueSelectionDecision):
            raise TypeError("coastline source join requires a typed generation decision")
        if not isinstance(region, TerrainRegionExtent) or not isinstance(budget, BodyCoverageAllocation):
            raise TypeError("coastline source join requires typed region and allocated budget")
        if not isinstance(region_coverage, RegionCoverage) or not isinstance(metadata, WaterSourceMetadata):
            raise TypeError("coastline source join requires captured coverage and metadata")
        if field_policy is not None and not isinstance(field_policy, (NoiseRecipe, PlateRecipe, PlateNoiseRecipe)):
            raise TypeError("coastline source join requires a typed field recipe")
        uid = source.location_uid
        try:
            wrapped = CoastlineWaterSource(value=source)
            request = LegacyAuthoredWaterGeometryRequest.model_validate(geometry_request, strict=True)
            mode = _ready_mode(source, request, context, admission, generation, metadata)
            # Reuse common input validation before any potentially expensive geometry.
            shared = WaterDesignInput[CoastlineWaterSource](strategy=context.strategy, source=wrapped,
                metadata=metadata, context=context, region=region, budget=budget, seed_root=request.seed_root,
                topology=request.topology, grid=request.grid, pre_hydrology=request.pre_hydrology,
                region_coverage=region_coverage)
            if context.strategy is Strategy.AUTHORED_REGION:
                if not wrapped.value.closed:
                    raise ValueError("an incomplete open line cannot supply authored body geometry")
                if field_policy is not None:
                    raise ValueError("authored coastline must not receive a procedural recipe")
                geometry = prepare_authored_water_geometry(request)
                return AuthoredWaterDesignInput[CoastlineWaterSource](source=shared.source, metadata=shared.metadata,
                    context=shared.context, region=shared.region, budget=shared.budget, seed_root=shared.seed_root,
                    topology=shared.topology, grid=shared.grid, pre_hydrology=shared.pre_hydrology,
                    region_coverage=shared.region_coverage, geometry=geometry)
            if mode is not HydrologyExecutionMode.AUTORESOLVE:
                raise ValueError("procedural coastline requires ready AUTORESOLVE before preparation")
            if field_policy is None:
                raise ValueError("procedural coastline requires an explicit field recipe")
            recipe = _RECIPE.validate_python(field_policy, strict=True)
            if recipe.strategy is not context.strategy:
                raise ValueError("field recipe must match the admitted strategy")
            if recipe.seed_root != request.seed_root or recipe.topology != fine_topology(request.topology, request.grid.fine_span):
                raise ValueError("field recipe must match the captured seed and fine topology")
            constraints = CoastlineConstraintPreparer().prepare(request)
            # Typed constructors retain the strategy/recipe pairing without raw kwargs.
            if isinstance(recipe, NoiseRecipe):
                return NoiseWaterDesignInput[CoastlineWaterSource](source=shared.source, metadata=shared.metadata,
                    context=shared.context, region=shared.region, budget=shared.budget, seed_root=shared.seed_root,
                    topology=shared.topology, grid=shared.grid, pre_hydrology=shared.pre_hydrology,
                    region_coverage=shared.region_coverage, constraints=constraints, field_policy=recipe, z_min=request.z_min)
            if isinstance(recipe, PlateRecipe):
                return PlateWaterDesignInput[CoastlineWaterSource](source=shared.source, metadata=shared.metadata,
                    context=shared.context, region=shared.region, budget=shared.budget, seed_root=shared.seed_root,
                    topology=shared.topology, grid=shared.grid, pre_hydrology=shared.pre_hydrology,
                    region_coverage=shared.region_coverage, constraints=constraints, field_policy=recipe, z_min=request.z_min)
            return PlateNoiseWaterDesignInput[CoastlineWaterSource](source=shared.source, metadata=shared.metadata,
                context=shared.context, region=shared.region, budget=shared.budget, seed_root=shared.seed_root,
                topology=shared.topology, grid=shared.grid, pre_hydrology=shared.pre_hydrology,
                region_coverage=shared.region_coverage, constraints=constraints, field_policy=recipe, z_min=request.z_min)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("water_source", uid), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error
