"""Request preparation composes domain factories; algorithms remain domain-owned."""

from collections.abc import Sequence
from functools import partial

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanWaitControl
from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
from app.application.worldData.generators.climate.registry import profile_for
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
from app.application.worldData.planning.composition.surfacePlanningAssembler import (
    SurfacePlanningAssembler, prepare_captured_bundle, report_surface_diagnostics,
)
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import (
    NoExtentSurfacePlanningView, SurfacePlanningView, SurfacePlanningViewKind,
)
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class SurfacePlanningEntry:
    def __init__(self, planning: SurfacePlanningAssembler, capture: SurfacePlanningCapture) -> None:
        self._planning, self._capture = planning, capture

    def capture_view(self, world: World, locations: Sequence[NamedLocation], *,
                     mode: ResolutionMode, mountain_templates: tuple[MountainTemplateInput, ...],
                     resolve_ctx: ResolveContext) -> SurfacePlanningView:
        return self._capture.capture(world, locations, mode=mode,
            mountain_templates=mountain_templates, resolve_ctx=resolve_ctx)

    def extent_status(self, view: SurfacePlanningView) -> SurfacePlanningViewKind:
        return view.kind

    def probe_extent(self, world: World, locations: Sequence[NamedLocation], *,
                     mode: ResolutionMode, mountain_templates: tuple[MountainTemplateInput, ...],
                     resolve_ctx: ResolveContext) -> SurfacePlanningViewKind:
        """Capture and report without preparing plans or projecting working maps."""
        view = self.capture_view(world, locations, mode=mode,
            mountain_templates=mountain_templates, resolve_ctx=resolve_ctx)
        report_surface_diagnostics(view.capture_diagnostics, resolve_ctx=resolve_ctx)
        return self.extent_status(view)

    def prepare_captured(self, view: SurfacePlanningView, *, world: World,
                         wait: PlanWaitControl, resolve_ctx: ResolveContext
                         ) -> tuple[SurfacePlanBundle, SurfaceWorkingMaps] | None:
        if view.world_uid != world.world_uid:
            raise ValueError("captured surface view belongs to another world")
        bundle = prepare_captured_bundle(view, planning=self._planning, wait=wait, resolve_ctx=resolve_ctx)
        if isinstance(view, NoExtentSurfacePlanningView):
            return None
        if bundle is None or bundle.world_uid != view.world_uid or bundle.view_revision != view.revision:
            raise ValueError("surface preparation returned a mismatched bundle")
        working = SurfaceWorkingMaps(
            climate=ClimateWorkingFields.from_plans(bundle.climate_base.payload,
                bundle.climate_local.payload, partial(profile_for, world)),
            terrain=TerrainWorkingFields.from_plan(bundle.terrain_base.payload),
            hydrology=HydrologyWorkingFields.from_plan(bundle.hydrology.payload, view.terrain_base.grid))
        return bundle, working

    def require_plan_inputs(
        self, world: World, locations: Sequence[NamedLocation], *,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
        mountain_templates: tuple[MountainTemplateInput, ...] = (),
    ) -> tuple[SurfacePlanBundle, SurfaceWorkingMaps]:
        """Application request boundary: one capture + one prepare per request."""
        ctx = resolve_ctx if resolve_ctx is not None else ResolveContext()
        mode = ResolutionMode.VALIDATE_ONLY if ctx.validate_only else ResolutionMode.RUNTIME
        view = self.capture_view(world, locations, mode=mode,
            mountain_templates=mountain_templates, resolve_ctx=ctx)
        result = self.prepare_captured(view, world=world, wait=wait, resolve_ctx=ctx)
        if result is None:
            raise ValueError("surface terrain context unavailable")
        return result

    def require_plan_bundle(
        self, world: World, locations: Sequence[NamedLocation], *,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
        mountain_templates: tuple[MountainTemplateInput, ...] = (),
    ) -> SurfacePlanBundle:
        return self.require_plan_inputs(world, locations, wait=wait,
            resolve_ctx=resolve_ctx, mountain_templates=mountain_templates)[0]
