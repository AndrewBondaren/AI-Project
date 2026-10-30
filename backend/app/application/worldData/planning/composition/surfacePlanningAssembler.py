"""Explicit phase calls over one frozen view; cache/scheduling delegate to PlanningService."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Generic
from typing_extensions import TypeVar

from pydantic import TypeAdapter

from app.application.jsonValidation.resolve import ResolveContext, report_issues, UnresolvedModelError
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition

from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader, PlanRegistry
from app.application.planning.service.planningService import PlanningService, PlanWaitControl
from app.application.worldData.planning.composition.planProviders import WorldPlanProviders, GeoWorldPlanProviders
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle, GeoSurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import (
    NoExtentSurfacePlanningView, ReadySurfacePlanningView, SurfacePlanningView, GeoSurfacePlanningView,
)
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanKey, PlanSlot, WorldPlanScope
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot


def _ref[T](slot: SurfacePlanSlot, envelope: PlanEnvelope[T]) -> PlanDependency:
    return PlanDependency(slot=PlanSlot(slot.value), ref=envelope.ref)


P = TypeVar("P", WorldPlanProviders, GeoWorldPlanProviders, default=WorldPlanProviders)


class SurfacePlanningAssembler(Generic[P]):
    def __init__(self, service: PlanningService, registry: PlanRegistry, providers: P) -> None:
        self._service, self._registry, self._providers = service, registry, providers

    def _build[I, T](self, view: ReadySurfacePlanningView | GeoSurfacePlanningView, contract: RegisteredPlanContract[I, T],
                      inputs: I, reader: PlanDependencyReader, deps: tuple[PlanDependency, ...],
                      wait: PlanWaitControl) -> PlanEnvelope[T]:
        scope = WorldPlanScope()
        deps = tuple(sorted(deps, key=lambda dep: dep.slot.encode("utf-8")))
        metadata = contract.metadata
        request = PlanRequest[I](key=PlanKey(world_uid=view.world_uid, scope=scope,
            contract_id=metadata.id, schema_version=metadata.schema_version,
            algorithm_version=metadata.algorithm_version,
            input_fingerprint=contract.fingerprint_inputs(view.world_uid, scope, inputs, deps)),
            inputs=inputs, dependencies=deps)
        return self._service.get_or_build(contract, request, reader, wait=wait)

    def prepare(self: SurfacePlanningAssembler[WorldPlanProviders], view: SurfacePlanningView, *,
                wait: PlanWaitControl) -> SurfacePlanBundle | None:
        wait.raise_if_cancelled()
        view = TypeAdapter[SurfacePlanningView](SurfacePlanningView).validate_python(view, strict=True)
        if isinstance(view, NoExtentSurfacePlanningView):
            return None
        p, S = self._providers, SurfacePlanSlot
        empty = PlanDependencyReader(self._registry)
        base = self._build(view, p.climate_base, view.climate_base, empty, (), wait)
        base_reader = empty.with_plan(PlanSlot(S.CLIMATE_BASE.value), p.climate_base, base)
        terrain = self._build(view, p.terrain_base, view.terrain_base, base_reader, (_ref(S.CLIMATE_BASE, base),), wait)
        terrain_reader = empty.with_plan(PlanSlot(S.TERRAIN_BASE.value), p.terrain_base, terrain)
        water = self._build(view, p.water_placement, view.water_placement, terrain_reader,
            (_ref(S.TERRAIN_BASE, terrain),), wait)
        relief_reader = base_reader.with_plan(PlanSlot(S.TERRAIN_BASE.value), p.terrain_base, terrain).with_plan(
            PlanSlot(S.WATER_PLACEMENT.value), p.water_placement, water)
        relief = self._build(view, p.relief, view.relief, relief_reader,
            (_ref(S.CLIMATE_BASE, base), _ref(S.TERRAIN_BASE, terrain), _ref(S.WATER_PLACEMENT, water)), wait)
        pre_reader = empty.with_plan(PlanSlot(S.RELIEF.value), p.relief, relief)
        routes = self._build(view, p.hydrology_routes, view.hydrology,
            pre_reader.with_plan(PlanSlot(S.WATER_PLACEMENT.value), p.water_placement, water),
            (_ref(S.RELIEF, relief), _ref(S.WATER_PLACEMENT, water)), wait)
        river_reader = pre_reader.with_plan(PlanSlot(S.HYDROLOGY_ROUTES.value), p.hydrology_routes, routes)
        river = self._build(view, p.river_relief, view.river_relief, river_reader,
            (_ref(S.RELIEF, relief), _ref(S.HYDROLOGY_ROUTES, routes)), wait)
        final = self._build(view, p.hydrology, view.hydrology_final,
            river_reader.with_plan(PlanSlot(S.RIVER_RELIEF.value), p.river_relief, river),
            (_ref(S.RELIEF, relief), _ref(S.HYDROLOGY_ROUTES, routes), _ref(S.RIVER_RELIEF, river)), wait)
        local = self._build(view, p.climate_local, view.climate_local,
            base_reader.with_plan(PlanSlot(S.HYDROLOGY.value), p.hydrology, final),
            (_ref(S.CLIMATE_BASE, base), _ref(S.HYDROLOGY, final)), wait)
        return SurfacePlanBundle(view_revision=view.revision, world_uid=view.world_uid,
            climate_base=base, terrain_base=terrain, water_placement=water, relief=relief,
            hydrology_routes=routes, river_relief=river, hydrology=final, climate_local=local)

    def prepare_geo(self: SurfacePlanningAssembler[GeoWorldPlanProviders],
                    view: GeoSurfacePlanningView | NoExtentSurfacePlanningView, *,
                    wait: PlanWaitControl) -> GeoSurfacePlanBundle | None:
        wait.raise_if_cancelled()
        view = TypeAdapter[GeoSurfacePlanningView | NoExtentSurfacePlanningView](
            GeoSurfacePlanningView | NoExtentSurfacePlanningView).validate_python(view, strict=True)
        if isinstance(view, NoExtentSurfacePlanningView):
            return None
        p, S = self._providers, SurfacePlanSlot
        empty = PlanDependencyReader(self._registry)
        base = self._build(view, p.climate_base, view.climate_base, empty, (), wait)
        base_reader = empty.with_plan(PlanSlot(S.CLIMATE_BASE.value), p.climate_base, base)
        terrain = self._build(view, p.terrain_base, view.terrain_base, base_reader, (_ref(S.CLIMATE_BASE, base),), wait)
        regions = self._build(view, p.terrain_regions, view.region_input, empty, (), wait)
        water_reader = empty.with_plan(PlanSlot(S.TERRAIN_BASE.value), p.terrain_base, terrain).with_plan(
            PlanSlot(S.TERRAIN_REGIONS.value), p.terrain_regions, regions)
        water = self._build(view, p.water_placement, view.water_placement, water_reader,
            (_ref(S.TERRAIN_BASE, terrain), _ref(S.TERRAIN_REGIONS, regions)), wait)
        relief_reader = base_reader.with_plan(PlanSlot(S.TERRAIN_BASE.value), p.terrain_base, terrain).with_plan(
            PlanSlot(S.WATER_PLACEMENT.value), p.water_placement, water)
        relief = self._build(view, p.relief, view.relief, relief_reader,
            (_ref(S.CLIMATE_BASE, base), _ref(S.TERRAIN_BASE, terrain), _ref(S.WATER_PLACEMENT, water)), wait)
        pre_reader = empty.with_plan(PlanSlot(S.RELIEF.value), p.relief, relief)
        routes = self._build(view, p.hydrology_routes, view.hydrology,
            pre_reader.with_plan(PlanSlot(S.WATER_PLACEMENT.value), p.water_placement, water),
            (_ref(S.RELIEF, relief), _ref(S.WATER_PLACEMENT, water)), wait)
        river_reader = pre_reader.with_plan(PlanSlot(S.HYDROLOGY_ROUTES.value), p.hydrology_routes, routes)
        river = self._build(view, p.river_relief, view.river_relief, river_reader,
            (_ref(S.RELIEF, relief), _ref(S.HYDROLOGY_ROUTES, routes)), wait)
        final = self._build(view, p.hydrology, view.hydrology_final,
            river_reader.with_plan(PlanSlot(S.RIVER_RELIEF.value), p.river_relief, river).with_plan(
                PlanSlot(S.WATER_PLACEMENT.value), p.water_placement, water),
            (_ref(S.RELIEF, relief), _ref(S.HYDROLOGY_ROUTES, routes), _ref(S.RIVER_RELIEF, river),
             _ref(S.WATER_PLACEMENT, water)), wait)
        final_reader = empty.with_plan(PlanSlot(S.HYDROLOGY.value), p.hydrology, final)
        local = self._build(view, p.climate_local, view.climate_local,
            base_reader.with_plan(PlanSlot(S.HYDROLOGY.value), p.hydrology, final),
            (_ref(S.CLIMATE_BASE, base), _ref(S.HYDROLOGY, final)), wait)
        boundaries = self._build(view, p.coastline_boundaries, view.boundary_input,
            final_reader.with_plan(PlanSlot(S.WATER_PLACEMENT.value), p.water_placement, water),
            (_ref(S.HYDROLOGY, final), _ref(S.WATER_PLACEMENT, water)), wait)
        support_reader = base_reader.with_plan(PlanSlot(S.TERRAIN_BASE.value), p.terrain_base, terrain).with_plan(
            PlanSlot(S.RELIEF.value), p.relief, relief).with_plan(PlanSlot(S.RIVER_RELIEF.value), p.river_relief, river).with_plan(
            PlanSlot(S.HYDROLOGY.value), p.hydrology, final).with_plan(PlanSlot(S.CLIMATE_LOCAL.value), p.climate_local, local)
        support = self._build(view, p.surface_support, view.surface_support, support_reader,
            (_ref(S.CLIMATE_BASE, base), _ref(S.TERRAIN_BASE, terrain), _ref(S.RELIEF, relief),
             _ref(S.RIVER_RELIEF, river), _ref(S.HYDROLOGY, final), _ref(S.CLIMATE_LOCAL, local)), wait)
        coating = self._build(view, p.coating, view.coating_input,
            final_reader.with_plan(PlanSlot(S.SURFACE_SUPPORT.value), p.surface_support, support),
            (_ref(S.HYDROLOGY, final), _ref(S.SURFACE_SUPPORT, support)), wait)
        return GeoSurfacePlanBundle(view_revision=view.revision, world_uid=view.world_uid,
            climate_base=base, terrain_base=terrain, terrain_regions=regions, water_placement=water, relief=relief,
            hydrology_routes=routes, river_relief=river, hydrology=final, climate_local=local,
            coastline_boundaries=boundaries, surface_support=support, coating=coating)


def prepare_captured_bundle(view: SurfacePlanningView, *, planning: SurfacePlanningAssembler,
                            wait: PlanWaitControl, resolve_ctx: ResolveContext) -> SurfacePlanBundle | None:
    """One report boundary for captured input and frozen plan diagnostics."""
    bundle = planning.prepare(view, wait=wait)
    diagnostics = list(view.capture_diagnostics)
    if bundle is not None:
        for envelope in (bundle.climate_base, bundle.terrain_base, bundle.water_placement,
                         bundle.relief, bundle.hydrology_routes, bundle.river_relief,
                         bundle.hydrology, bundle.climate_local):
            diagnostics.extend(envelope.diagnostics)
    report_surface_diagnostics(diagnostics, resolve_ctx=resolve_ctx)
    return bundle


def prepare_captured_geo_bundle(view: GeoSurfacePlanningView | NoExtentSurfacePlanningView, *,
                                planning: SurfacePlanningAssembler[GeoWorldPlanProviders],
                                wait: PlanWaitControl, resolve_ctx: ResolveContext) -> GeoSurfacePlanBundle | None:
    """Report captured and cached GEO diagnostics through the shared reporting policy."""
    bundle = planning.prepare_geo(view, wait=wait)
    diagnostics = list(view.capture_diagnostics)
    if bundle is not None:
        for envelope in (bundle.climate_base, bundle.terrain_base, bundle.terrain_regions,
                         bundle.water_placement, bundle.relief, bundle.hydrology_routes,
                         bundle.river_relief, bundle.hydrology, bundle.climate_local,
                         bundle.coastline_boundaries, bundle.surface_support, bundle.coating):
            diagnostics.extend(envelope.diagnostics)
    report_surface_diagnostics(diagnostics, resolve_ctx=resolve_ctx)
    return bundle


def report_surface_diagnostics(diagnostics: Iterable[PlanDiagnostic], *,
                               resolve_ctx: ResolveContext) -> None:
    """Shared reporting policy for capture-only probes and prepared plans."""
    diagnostics = tuple(dict.fromkeys(diagnostics))
    issues = tuple(item.issue for item in diagnostics
        if item.disposition is not PlanDiagnosticDisposition.NOTICE)
    report_issues(resolve_ctx, (issue for issue in issues if issue not in resolve_ctx.errors))
    for item in diagnostics:
        if item.disposition is PlanDiagnosticDisposition.NOTICE and not resolve_ctx.collect_only:
            logging.getLogger(__name__).info("surface planning | path=%s code=%s | %s",
                item.issue.path, item.issue.code, item.issue.message)
    if resolve_ctx.validate_only and issues:
        raise UnresolvedModelError(list(dict.fromkeys(issues)))
