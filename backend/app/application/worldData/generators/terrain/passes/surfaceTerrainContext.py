"""Compatibility entry: capture once, then delegate to surface planning."""

from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanWaitControl
from app.application.worldData.planning.composition.surfacePlanningAssembler import (
    SurfacePlanningAssembler, prepare_captured_context, prepare_captured_bundle,
)
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
from app.application.worldData.planning.legacy.surfaceTerrainContext import SurfaceTerrainContext as SurfaceTerrainContext
from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def prepare_surface_terrain_context(
    world: World, locations: list[NamedLocation], *,
    planning: SurfacePlanningAssembler, capture: SurfacePlanningCapture, wait: PlanWaitControl,
    nodes: list[ConnectionNode] | None = None, edges: list[ConnectionEdge] | None = None,
    resolve_ctx: ResolveContext | None = None,
    mountain_templates: tuple[MountainTemplateInput, ...] = (),
) -> SurfaceTerrainContext | None:
    ctx = resolve_ctx if resolve_ctx is not None else ResolveContext()
    mode = ResolutionMode.VALIDATE_ONLY if ctx.validate_only else ResolutionMode.RUNTIME
    view = capture.capture(world, locations, mode=mode,
        mountain_templates=mountain_templates, resolve_ctx=ctx)
    return prepare_captured_context(view, world=world, planning=planning, capture=capture, wait=wait, resolve_ctx=ctx)


def require_surface_terrain_context(
    world: World, locations: list[NamedLocation], *,
    planning: SurfacePlanningAssembler, capture: SurfacePlanningCapture, wait: PlanWaitControl,
    nodes: list[ConnectionNode] | None = None, edges: list[ConnectionEdge] | None = None,
    resolve_ctx: ResolveContext | None = None,
    mountain_templates: tuple[MountainTemplateInput, ...] = (),
) -> SurfaceTerrainContext:
    result = prepare_surface_terrain_context(world, locations, planning=planning, capture=capture,
        wait=wait, nodes=nodes, edges=edges, resolve_ctx=resolve_ctx, mountain_templates=mountain_templates)
    if result is None:
        raise ValueError("surface terrain context unavailable")
    return result


def require_surface_plan_inputs(
    world: World, locations: list[NamedLocation], *,
    planning: SurfacePlanningAssembler, capture: SurfacePlanningCapture, wait: PlanWaitControl,
    nodes: list[ConnectionNode] | None = None, edges: list[ConnectionEdge] | None = None,
    resolve_ctx: ResolveContext | None = None,
    mountain_templates: tuple[MountainTemplateInput, ...] = (),
) -> tuple[SurfacePlanBundle, SurfaceWorkingMaps]:
    """Standalone entry boundary; downstream refine reuses this single capture."""
    ctx = resolve_ctx if resolve_ctx is not None else ResolveContext()
    mode = ResolutionMode.VALIDATE_ONLY if ctx.validate_only else ResolutionMode.RUNTIME
    view = capture.capture(world, locations, mode=mode,
        mountain_templates=mountain_templates, resolve_ctx=ctx)
    result = SurfacePlanningEntry(planning, capture).prepare_captured(
        view, world=world, wait=wait, resolve_ctx=ctx)
    if result is None:
        raise ValueError("surface terrain context unavailable")
    return result


def require_surface_plan_bundle(
    world: World, locations: list[NamedLocation], *,
    planning: SurfacePlanningAssembler, capture: SurfacePlanningCapture, wait: PlanWaitControl,
    nodes: list[ConnectionNode] | None = None, edges: list[ConnectionEdge] | None = None,
    resolve_ctx: ResolveContext | None = None,
    mountain_templates: tuple[MountainTemplateInput, ...] = (),
) -> SurfacePlanBundle:
    return require_surface_plan_inputs(world, locations, planning=planning, capture=capture,
        wait=wait, nodes=nodes, edges=edges, resolve_ctx=resolve_ctx,
        mountain_templates=mountain_templates)[0]
