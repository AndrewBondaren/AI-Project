"""Consume accepted water geometry and project the existing physical water kernel."""

from pydantic import TypeAdapter

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.types import resolve_scopes
from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.hydrologyPlan import coarse_order, require_map
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.spatial.grid.coordinateTypes import FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan, GeoWaterPlacementPlan
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


_DECISIONS = TypeAdapter[tuple[tuple[Category, HydrologyGenerationDecision], ...]](
    tuple[tuple[Category, HydrologyGenerationDecision], ...])


class WaterBodyPlanner:
    def plan(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput,
             surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], placement: WaterPlacementPlan,
             control: PlanBuildControl) -> PlanBuildResult[OpenWaterPlan]:
        control.raise_if_shutdown()
        if inputs.topology != placement.topology:
            raise PlanBuildFailure((FieldPathError(("placement",),
                "water planning requires the captured placement topology"),))
        self._require_surface(surface_z, inputs.topology, inputs.z_min, inputs.z_max)
        scopes = resolve_scopes(inputs.scopes)
        seas = bool(scopes & {HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN})
        lakes = HydrologyScope.LAKES in scopes
        if not inputs.enabled or not (seas or lakes):
            return PlanBuildResult[OpenWaterPlan](payload=OpenWaterPlan(
                coarse_open_water=(), water_bodies=(), physical_unions=(), source_mapping=SourceBodyMapping(entries=())), diagnostics=())
        return self._materialize(world_uid=world_uid, inputs=inputs, surface_z=surface_z,
            specs=self._select_specs(inputs, placement.basin_specs),
            auto_seas=bool(seas and inputs.seas.enabled and (
                inputs.seas.autoresolve_coastal_sea or inputs.seas.autoresolve_open_ocean)),
            auto_lakes=bool(lakes and inputs.lakes.enabled and inputs.lakes.autoresolve),
            allowed_kinds=frozenset(([BasinKind.LAKE] if lakes and inputs.lakes.enabled else []) + (
                [BasinKind.SEA, BasinKind.OCEAN, BasinKind.INLAND_SEA] if seas and inputs.seas.enabled else [])),
            control=control)

    def plan_geo(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                 surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], placement: GeoWaterPlacementPlan,
                 classification_decisions: tuple[tuple[Category, HydrologyGenerationDecision], ...],
                 control: PlanBuildControl) -> PlanBuildResult[OpenWaterPlan]:
        control.raise_if_shutdown()
        try:
            placement = GeoWaterPlacementPlan.model_validate(placement)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("placement",), str(error)),)) from error
        if inputs.topology != placement.topology:
            raise PlanBuildFailure((FieldPathError(("placement",),
                "water planning requires the captured placement topology"),))
        self._require_surface(surface_z, inputs.topology, inputs.z_min, inputs.z_max)
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
        if all(mode is Mode.DISABLED for mode in modes.values()):
            return PlanBuildResult[OpenWaterPlan](payload=OpenWaterPlan(
                coarse_open_water=(), water_bodies=(), physical_unions=(),
                source_mapping=SourceBodyMapping(entries=())), diagnostics=())
        # Accepted BasinSpecs already contain the one placement decision. Category
        # classification never repeats source admission or synthesizes designed seas.
        return self._materialize(world_uid=world_uid, inputs=inputs, surface_z=surface_z,
            specs=placement.basin_specs, auto_seas=False,
            auto_lakes=modes[Category.LAKE] is Mode.AUTORESOLVE and BasinKind.LAKE in inputs.allowed_body_kinds,
            allowed_kinds=inputs.allowed_body_kinds, control=control)

    def _materialize(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput | GeoHydrologyPlanInput,
                     surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], specs: tuple[BasinSpec, ...],
                     auto_seas: bool, auto_lakes: bool, allowed_kinds: frozenset[BasinKind],
                     control: PlanBuildControl) -> PlanBuildResult[OpenWaterPlan]:
        bounds = inputs.topology.bounds
        heightmap = SurfaceHeightmap(world_uid, GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max),
            {(cell.gx, cell.gy): int(z) for cell, z in surface_z})
        policy = WorldHydrology(default_water_level=inputs.default_water_level,
            default_seas=inputs.seas, default_lakes=inputs.lakes, default_rivers=inputs.rivers)
        diagnostics: list[PlanDiagnostic] = []
        ctx = ResolveContext(collect_only=True, validate_only=inputs.resolution_mode is ResolutionMode.VALIDATE_ONLY)
        control.raise_if_shutdown()
        water = assemble_water_bodies(heightmap, specs,
            inputs.topology, policy, change_uid=inputs.change_uid,
            auto_seas=auto_seas, auto_lakes=auto_lakes, allowed_kinds=allowed_kinds,
            ctx=ctx, emit=diagnostics.append)
        control.raise_if_shutdown()
        cells = water.materialized.by_cell
        return PlanBuildResult[OpenWaterPlan](payload=OpenWaterPlan(coarse_open_water=tuple(
            (SurfaceGridCoord(GridX(x), GridY(y)), cells[(x, y)]) for x, y in sorted(cells, key=lambda cell: (cell[1], cell[0]))),
            water_bodies=water.materialized.bodies, physical_unions=water.physical_unions,
            source_mapping=water.materialized.source_mapping),
            diagnostics=tuple(dict.fromkeys(diagnostics)))

    def _select_specs(self, inputs: HydrologyPlanInput, specs: tuple[BasinSpec, ...]) -> tuple[BasinSpec, ...]:
        if not inputs.enabled:
            return ()
        scopes = resolve_scopes(inputs.scopes)
        seas = bool(scopes & {HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN}) and inputs.seas.enabled
        lakes = HydrologyScope.LAKES in scopes and inputs.lakes.enabled
        return tuple(spec for spec in specs if (lakes if spec.kind is BasinKind.LAKE else seas))

    def _require_surface(self, surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], topology: WorldTopology,
                         z_min: FineZ, z_max: FineZ) -> None:
        try:
            require_map(surface_z, coarse_order)
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("surface_z",), str(error)),)) from error
        bounds = topology.bounds
        if (len(surface_z) != bounds.width * bounds.height or any(
                topology.canonicalize(cell.gx, cell.gy) != (cell.gx, cell.gy) or not z_min <= z <= z_max
                for cell, z in surface_z)):
            raise PlanBuildFailure((FieldPathError(("surface_z",),
                "water planning requires complete canonical pre-river heights within world z bounds"),))
