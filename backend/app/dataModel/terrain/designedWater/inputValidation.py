"""Cross-field validation of captured water design inputs, in diagnostic order."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError
from pydantic_core import InitErrorDetails

from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource
from app.dataModel.planning.identity.planKey import RegionPlanScope
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.fineTopology import fine_topology

if TYPE_CHECKING:
    from app.dataModel.terrain.designedWater.input import (
        ConstraintsT, NativeCoastlineStrategyContext, SourceT, SurfaceT, _WaterDesignContext,
    )


class InputIssues:
    def __init__(self) -> None:
        self._issues: list[InitErrorDetails] = []

    def report[M: BaseModel, T](self, model: M, select: Callable[[M], T], message: str, *parent: str) -> None:
        field = bind_field(FieldRef(lambda: type(model), select)).field
        self._issues.append(InitErrorDetails(type="value_error", loc=(*parent, field),
                                             input=select(model), ctx={"error": ValueError(message)}))

    def raise_if_any(self, title: str) -> None:
        if self._issues:
            raise ValidationError.from_exception_data(title, self._issues)


def check_constraints(data: _WaterDesignContext[SourceT, SurfaceT, ConstraintsT], issues: InputIssues) -> None:
    constraints = data.constraints
    source = data.source
    if constraints is not None:
        if constraints.source != source:
            issues.report(constraints, lambda c: c.source, "constraints source mismatch", "constraints")
        if constraints.pre_hydrology_ref != data.pre_hydrology_ref:
            issues.report(constraints, lambda c: c.pre_hydrology_ref, "constraints terrain revision mismatch", "constraints")
        if constraints.grid != data.grid:
            issues.report(constraints, lambda c: c.grid, "constraints grid mismatch", "constraints")
        if any(data.topology.canonicalize(*cell) != cell for cell in constraints.allowed_cells):
            issues.report(constraints, lambda v: v.allowed_cells, "constraints require canonical coordinates", "constraints")


def check_source(data: _WaterDesignContext[SourceT, SurfaceT, ConstraintsT], issues: InputIssues) -> None:
    source, metadata = data.source, data.metadata
    if isinstance(source, (AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource)):
        value = source.value
        uid = source.value.source_uid if isinstance(source, ProceduralSource) else source.value.location_uid
        if uid != metadata.source_uid:
            issues.report(metadata, lambda m: m.source_uid, "metadata source UID mismatch", "metadata")
        if source.kind != metadata.source_kind:
            issues.report(metadata, lambda m: m.source_kind, "metadata source kind mismatch", "metadata")
        if value.liquid != metadata.liquid:
            issues.report(metadata, lambda m: m.liquid, "metadata liquid mismatch", "metadata")
        kind = BasinKind.LAKE if isinstance(source, AuthoredLakeSource) else source.value.kind
        if kind != metadata.body_kind:
            issues.report(metadata, lambda v: v.body_kind, "source and metadata body kind mismatch", "metadata")
        if isinstance(source, (AuthoredBasinSource, ProceduralSource)):
            if source.value.z_water_level is not None and source.value.z_water_level != metadata.level:
                issues.report(metadata, lambda v: v.level, "metadata must preserve explicit source water level", "metadata")
        if data.budget.source_uid != uid:
            issues.report(data.budget, lambda b: b.source_uid, "allocation source mismatch", "budget")
    else:
        issues.report(data, lambda v: v.source, "water input requires a supported typed water source")
    if data.context.strategy != data.strategy:
        issues.report(data.context, lambda v: v.strategy, "resolved context and effective strategy mismatch", "context")


def check_region(data: _WaterDesignContext[SourceT, SurfaceT, ConstraintsT], issues: InputIssues) -> None:
    source = data.source
    if data.budget.generation_region_uid != data.region.region_uid:
        issues.report(data.budget, lambda b: b.generation_region_uid, "allocation region mismatch", "budget")
    if isinstance(source, ProceduralSource) and source.value.generation_region_uid != data.region.region_uid:
        issues.report(source.value, lambda v: v.generation_region_uid, "procedural region binding mismatch", "source", "value")
    if data.region_coverage.region_uid != data.region.region_uid:
        issues.report(data.region_coverage, lambda v: v.region_uid, "coverage identity mismatch", "region_coverage")
    if sum(s.x1 - s.x0 for s in data.region_coverage.spans) != data.region.generation_area_fine2:
        issues.report(data.region, lambda v: v.generation_area_fine2, "coverage area mismatch", "region")
    if data.budget.requested_fine2 > data.region.generation_area_fine2:
        issues.report(data.budget, lambda v: v.requested_fine2, "request exceeds generation area", "budget")
    surface = data.pre_hydrology.payload
    fine_bounds = (data.topology if isinstance(surface, FineSurfaceWindow)
                   else fine_topology(data.topology, data.grid.fine_span)).bounds
    if any(not fine_bounds.contains(s.x0, s.y) or not fine_bounds.contains(s.x1 - 1, s.y)
           for s in data.region_coverage.spans):
        issues.report(data.region_coverage, lambda v: v.spans, "coverage must use canonical world fine coordinates", "region_coverage")


def check_window(data: _WaterDesignContext[SourceT, SurfaceT, ConstraintsT], issues: InputIssues) -> None:
    surface = data.pre_hydrology.payload
    bounds = data.topology.bounds
    if isinstance(surface, FineSurfaceWindow):
        if surface.topology != data.topology or len(surface.surface_z) != bounds.width * bounds.height:
            issues.report(data.pre_hydrology, lambda v: v.payload, "native design requires the complete fine window", "pre_hydrology")
        if any(d.ref.key.scope != data.pre_hydrology_ref.key.scope for d in data.pre_hydrology.dependencies):
            issues.report(data.pre_hydrology, lambda v: v.dependencies, "native window dependencies must share its scope", "pre_hydrology")
    else:
        bbox = surface.bbox
        if (bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max) != (
                bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max):
            issues.report(surface, lambda v: v.bbox, "pre-hydrology surface must match the coarse topology", "pre_hydrology", "payload")
    key = data.pre_hydrology_ref.key
    if isinstance(key.scope, RegionPlanScope) and key.scope.region_uid != data.region.region_uid:
        issues.report(data.pre_hydrology, lambda v: v.ref, "pre-hydrology ref belongs to another region", "pre_hydrology")
    if any(d.ref.key.world_uid != key.world_uid for d in data.pre_hydrology.dependencies):
        issues.report(data.pre_hydrology, lambda v: v.dependencies, "pre-hydrology dependencies belong to another world", "pre_hydrology")


def check_native_recipe(data: NativeCoastlineStrategyContext, issues: InputIssues) -> None:
    if not data.context.autoresolve:
        issues.report(data.context, lambda c: c.autoresolve, "native coastline requires autoresolve", "context")
    recipe = data.field_policy
    if recipe.strategy != data.strategy:
        issues.report(recipe, lambda r: r.strategy, "recipe must match the admitted strategy", "field_policy")
    if recipe.seed_root != data.seed_root:
        issues.report(recipe, lambda r: r.seed_root, "recipe must match the captured seed", "field_policy")
    if recipe.topology != data.topology:
        issues.report(recipe, lambda r: r.topology, "recipe must use the captured fine topology", "field_policy")
    if data.metadata.level <= data.z_min:
        issues.report(data.metadata, lambda m: m.level, "water level must exceed the lower bound", "metadata")
    if any(z < data.z_min for _, z in data.pre_hydrology.payload.surface_z):
        issues.report(data, lambda v: v.z_min, "fine window extends below the captured lower bound")
