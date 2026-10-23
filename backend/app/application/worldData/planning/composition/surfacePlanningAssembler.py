"""Explicit phase calls over one frozen view; cache/scheduling delegate to PlanningService."""

from pydantic import TypeAdapter

from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader, PlanRegistry
from app.application.planning.service.planningService import PlanningService, PlanWaitControl
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.planning.composition.planProviders import WorldPlanProviders
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import (
    NoExtentSurfacePlanningView, ReadySurfacePlanningView, SurfacePlanningView, SurfaceTerrainContext,
)
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanKey, PlanSlot, WorldPlanScope
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot


def _ref[T](slot: SurfacePlanSlot, envelope: PlanEnvelope[T]) -> PlanDependency:
    return PlanDependency(slot=PlanSlot(slot.value), ref=envelope.ref)


class SurfacePlanningAssembler:
    def __init__(self, service: PlanningService, registry: PlanRegistry, providers: WorldPlanProviders) -> None:
        self._service, self._registry, self._providers = service, registry, providers

    def _build[I, T](self, view: ReadySurfacePlanningView, contract: RegisteredPlanContract[I, T],
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

    def prepare(self, view: SurfacePlanningView, *, wait: PlanWaitControl) -> SurfacePlanBundle | None:
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


def to_legacy_context(bundle: SurfacePlanBundle) -> SurfaceTerrainContext:
    bundle = SurfacePlanBundle.model_validate(bundle)
    base, final = bundle.climate_base.payload, bundle.hydrology.payload
    surface: dict[tuple[int, int], int] = {(cell.gx, cell.gy): z for cell, z in final.coarse_surface_z}
    return SurfaceTerrainContext(
        pole_field=ClimatePoleField(base.poles, base.bbox),
        local_field=ClimateAnchorField(bundle.climate_local.payload.anchors),
        coarse_hm=SurfaceHeightmap(bundle.world_uid, bundle.terrain_base.payload.bbox, dict(surface)),
        coarse_hydro={(cell.gx, cell.gy): value for cell, value in final.coarse_hydro},
        sparse_fine_hydro=dict(final.sparse_fine_hydro), fine_z_overrides=dict(final.fine_z_overrides),
        coarse_relief_z={(cell.gx, cell.gy): z for cell, z in bundle.terrain_base.payload.surface_z},
        coarse_surface_z=dict(surface))
