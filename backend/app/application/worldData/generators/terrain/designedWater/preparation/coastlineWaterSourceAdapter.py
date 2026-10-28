"""Join captured inputs for one coastline source; decisions remain common policy."""

from pydantic import TypeAdapter

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
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, ValueSelectionDecision
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe, WaterFieldRecipe
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometryRequest
from app.dataModel.terrain.designedWater.input import (
    AuthoredWaterDesignInput, CoastlineWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput,
    PlateNoiseWaterDesignInput, WaterDesignInput,
)
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy, WaterDesignIssueCode
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

_RECIPE = TypeAdapter(WaterFieldRecipe)
_GENERATION = TypeAdapter(HydrologyGenerationDecision)


class CoastlineWaterSourceAdapter:
    """Validate the ready join, delegate geometry, bind the existing strategy input.

    The caller owns captured inputs and early lifecycle admission. This adapter
    neither executes policy/strategy nor allocates coverage or writes terrain.
    """

    def prepare_source(
        self, source: DeclaredCoastline, *, geometry_request: AuthoredWaterGeometryRequest,
        context: ResolvedWaterGenerationContext, generation: HydrologyGenerationDecision,
        region: TerrainRegionExtent, budget: BodyCoverageAllocation, region_coverage: RegionCoverage,
        metadata: WaterSourceMetadata, admission: PlacementAdmissionInput, field_policy: WaterFieldRecipe | None,
    ) -> CoastlineWaterDesignInput:
        if not isinstance(source, DeclaredCoastline) or not isinstance(geometry_request, AuthoredWaterGeometryRequest):
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
            request = AuthoredWaterGeometryRequest.model_validate(geometry_request, strict=True)
            context = ResolvedWaterGenerationContext.model_validate(context, strict=True)
            admission = PlacementAdmissionInput.model_validate(admission, strict=True)
            decision = ObjectAdmissionDecision[Strategy, WaterPolicyReason].model_validate(admission.decision, strict=True)
            generation = _GENERATION.validate_python(generation, strict=True)
            if decision.state is not PolicyState.READY or generation.state is not PolicyState.READY:
                raise ValueError("coastline geometry requires ready admission and generation decisions")
            if request.source != wrapped:
                raise ValueError("geometry request must capture the same complete coastline source")
            identity = admission.header.identity
            if identity.source_uid != uid or identity.world_uid != request.pre_hydrology.ref.key.world_uid:
                raise ValueError("admission source/world must match the captured terrain and source")
            if admission.header.mode is not PlacementMode.ABSOLUTE:
                raise ValueError("authored coastline path requires absolute placement")
            if any(d.target_uid in (identity.source_uid, identity.region_uid) for d in admission.header.dependencies):
                raise ValueError("water source cannot depend on itself or its future water")
            if decision.require_behavior() is not context.strategy:
                raise ValueError("admission strategy must match the resolved generation context")
            mode = generation.require_behavior()
            if mode not in (HydrologyExecutionMode.DECLARED_ONLY, HydrologyExecutionMode.AUTORESOLVE):
                raise ValueError("ready generation requires DECLARED_ONLY or AUTORESOLVE")
            if (mode is HydrologyExecutionMode.AUTORESOLVE) is not context.autoresolve:
                raise ValueError("generation decision must match resolved context autoresolve")
            if metadata.source_kind is not WaterDesignSourceKind.COASTLINE:
                raise ValueError("coastline metadata must retain the source origin")
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
                    region_coverage=shared.region_coverage, constraints=constraints, field_policy=recipe)
            if isinstance(recipe, PlateRecipe):
                return PlateWaterDesignInput[CoastlineWaterSource](source=shared.source, metadata=shared.metadata,
                    context=shared.context, region=shared.region, budget=shared.budget, seed_root=shared.seed_root,
                    topology=shared.topology, grid=shared.grid, pre_hydrology=shared.pre_hydrology,
                    region_coverage=shared.region_coverage, constraints=constraints, field_policy=recipe)
            return PlateNoiseWaterDesignInput[CoastlineWaterSource](source=shared.source, metadata=shared.metadata,
                context=shared.context, region=shared.region, budget=shared.budget, seed_root=shared.seed_root,
                topology=shared.topology, grid=shared.grid, pre_hydrology=shared.pre_hydrology,
                region_coverage=shared.region_coverage, constraints=constraints, field_policy=recipe)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("water_source", uid), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error
