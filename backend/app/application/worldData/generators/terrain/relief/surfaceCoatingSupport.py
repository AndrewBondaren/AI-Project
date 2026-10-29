"""Read-only terrain evidence and common-policy binding; activation belongs to G10-A."""
from dataclasses import dataclass

from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl
from app.application.policy.declarations.compiler import compile_value_policy
from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.terrain.relief.surfaceCoating.geometry import observe_sides
from app.application.worldData.generators.terrain.relief.surfaceCoating.sources import SupportSources
from app.application.worldData.pack.bake.lightGrid.coords import fine_to_light, light_to_macro_local
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs, PolicySource
from app.dataModel.policy.policyFacts import KnownFact, UnknownFact
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineXY, LightCellRef
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import (
    CoatingCellPlan, CoatingPlan, SurfaceAspect, SurfaceCoatingAction, SurfaceCoatingFacts,
    SurfaceCoatingIssueCode, SurfaceSupportPlan,
    SURFACE_SUPPORT_SLOT,
)
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingPolicyDefinition import (
    SURFACE_COATING_POLICY, SurfaceCoatingSelection, SurfaceCoatingTargetFacts,
)
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import CoatingPlanInput, SurfaceSupportInput
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


@dataclass(frozen=True)
class SurfaceSupportDependencies:
    climate_base: PlanEnvelope[ClimateBasePlan]
    terrain_base: PlanEnvelope[TerrainPlan]
    relief: PlanEnvelope[ReliefPlan]
    river_relief: PlanEnvelope[RiverReliefPlan]
    hydrology: PlanEnvelope[HydrologyPlan]
    climate_local: PlanEnvelope[ClimateLocalPlan]

    def require_coherent(self, request: PlanRequest[SurfaceSupportInput]) -> None:
        supplied = {name: getattr(self, name).ref for name in self.__dataclass_fields__}
        declared = {d.slot: d.ref for d in request.dependencies}
        if declared != supplied or any(ref.key.world_uid != request.key.world_uid or
                ref.key.scope != request.key.scope for ref in supplied.values()):
            raise ValueError("support requires exact same-world/scope dependency references")
        # A final water revision must prove its post-river heights, never a routes envelope.
        for name in ("hydrology", "climate_local"):
            envelope = getattr(self, name)
            for dependency in envelope.dependencies:
                if dependency.slot in supplied and dependency.ref != supplied[dependency.slot]:
                    raise ValueError("support dependency revisions are incoherent")
        if not any(d.slot == "river_relief" and d.ref == self.river_relief.ref for d in self.hydrology.dependencies):
            raise ValueError("final hydrology must prove its post-river surface reference")
        if not any(d.slot == "relief" and d.ref == self.relief.ref for d in self.river_relief.dependencies):
            raise ValueError("post-river surface must bind the supplied pre-river relief")
        if not any(d.slot == "hydrology" and d.ref == self.hydrology.ref for d in self.climate_local.dependencies):
            raise ValueError("local climate must bind the same final hydrology")


def unknown_support(cell: FineXY, channel: str, message: str) -> UnknownFact:
    return UnknownFact(issue=FieldPathError(("surface_support", cell[0], cell[1], channel), message,
        code=SurfaceCoatingIssueCode.UNKNOWN_SUPPORT.value))


def shore_cells(hydrology: HydrologyPlan, span: int) -> dict[FineXY, MapCellHydrology]:
    """Final sparse fine observations override the coarse projection, including dry overrides."""
    result: dict[FineXY, MapCellHydrology] = {}
    for cell, value in hydrology.coarse_hydro:
        if value.role is HydrologyCellRole.SHORE:
            for y in range(cell.gy * span, (cell.gy + 1) * span):
                for x in range(cell.gx * span, (cell.gx + 1) * span):
                    result[(FineX(x), FineY(y))] = value
    for cell, value in hydrology.sparse_fine_hydro:
        if value.role is HydrologyCellRole.SHORE:
            result[cell] = value
        else:
            result.pop(cell, None)
    return result


class SurfaceCoatingSupportProvider:
    def __init__(self, climate_base: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan],
                 terrain_base: RegisteredPlanContract[TerrainBaseInput, TerrainPlan],
                 relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
                 river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan],
                 hydrology: RegisteredPlanContract[HydrologyFinalInput, HydrologyPlan],
                 climate_local: RegisteredPlanContract[ClimateLocalInput, ClimateLocalPlan]):
        self._climate_base, self._terrain_base, self._relief = climate_base, terrain_base, relief
        self._river_relief, self._hydrology, self._climate_local = river_relief, hydrology, climate_local

    @staticmethod
    def facts(request: PlanRequest[SurfaceSupportInput], dependencies: SurfaceSupportDependencies, *,
              cells: RegionCoverage) -> tuple[SurfaceCoatingFacts, ...]:
        dependencies.require_coherent(request)
        inputs = request.inputs
        sources = SupportSources(request.key.world_uid, inputs, dependencies.climate_base.payload,
            dependencies.climate_local.payload, dependencies.terrain_base.payload, dependencies.hydrology.payload)
        topology = fine_topology(inputs.topology, inputs.grid.fine_span)
        layout = dependencies.relief.payload.mountain_layout
        templates = dict(inputs.templates)
        membership_valid = all(t.template_uid in templates and
            templates[t.template_uid].side_recipe == t.side_recipe for t in layout.templates)
        # Layout side stamps prove geometry, not the material of attached structures.
        # Without a frozen structural material proof those candidates stay unknown.
        bare_members = all(not templates[t.template_uid].structure_refs and
            templates[t.template_uid].structure_canal is None for t in layout.templates
            if t.template_uid in templates)
        surface = {cell for cell, _ in dependencies.river_relief.payload.surface_z}
        macro_extent = {(cell.gx, cell.gy) for cell in surface}
        entries = {e.key: e for e in inputs.terrain_entries}
        materials = {m.key: m for m in inputs.materials}
        carved = {cell for bed in dependencies.river_relief.payload.fine_beds for cell, _ in bed.bed_z}
        ravines = {c.cell for c in dependencies.relief.payload.light.ravine_cells}
        light_mountains = {c.cell for c in dependencies.relief.payload.light.mountain_cells}
        result: list[SurfaceCoatingFacts] = []
        for span in cells.spans:
            for x in range(span.x0, span.x1):
                cell = (FineX(x), FineY(span.y))
                if topology.canonicalize(*cell) != cell:
                    raise ValueError("support cells require canonical fine coordinates")
                in_surface = (x // inputs.grid.fine_span, span.y // inputs.grid.fine_span) in macro_extent
                observation = observe_sides(layout, cell, light_span=float(sources.scale.light_span), topology=topology) if in_surface else None
                key = sources.terrain_at(cell)
                light_cell = LightCellRef(*light_to_macro_local(*fine_to_light(*cell, sources.scale), sources.scale))
                projected_key = (dependencies.relief.payload.light.ravine_terrain if light_cell in ravines else
                                 layout.terrain_key if observation is not None or light_cell in light_mountains else None)
                projected_entry = entries.get(projected_key) if projected_key is not None else None
                if projected_key is not None and (key is None or projected_entry is None or projected_entry.merge_rank >= entries[key].merge_rank):
                    key = projected_key
                path: tuple[str | int, ...] = ("terrain_entries", key if key is not None else "missing", "default_material")
                entry = entries.get(key) if key is not None else None
                material_key = entry.default_material if entry is not None and cell not in carved and (observation is None or bare_members) else None
                material = materials.get(material_key) if material_key is not None else None
                unknown_geometry = unknown_support(cell, "geometry", "required captured geometry/member evidence is unavailable")
                unproven_projection = observation is None and (light_cell in ravines or light_cell in light_mountains)
                geometry_known = in_surface and (observation is None or membership_valid) and cell not in carved and not unproven_projection
                aspect = (KnownFact(value=observation.aspect if observation else SurfaceAspect.HORIZONTAL)
                          if geometry_known else unknown_geometry)
                side = KnownFact(value=observation.side_kind) if geometry_known and observation is not None else unknown_geometry
                result.append(SurfaceCoatingFacts(world_uid=request.key.world_uid,
                    support_input_fingerprint=request.key.input_fingerprint, cell=cell,
                    face=observation.face if observation is not None else None, aspect=aspect, side_kind=side,
                    material=KnownFact(value=material_key) if material_key is not None and material is not None else
                        unknown_support(cell, "material", "captured terrain/material membership is unavailable"),
                    substrate=KnownFact(value=material.substrate) if material is not None and material.substrate is not None else
                        unknown_support(cell, "substrate", "captured material has no substrate classification"),
                    geometry_ref=dependencies.river_relief.ref, material_source_path=path))
        return tuple(result)

    def build(self, request: PlanRequest[SurfaceSupportInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[SurfaceSupportPlan]:
        control.raise_if_shutdown()
        dep = SurfaceSupportDependencies(
            dependencies.require(PlanSlot(SurfacePlanSlot.CLIMATE_BASE.value), self._climate_base),
            dependencies.require(PlanSlot(SurfacePlanSlot.TERRAIN_BASE.value), self._terrain_base),
            dependencies.require(PlanSlot(SurfacePlanSlot.RELIEF.value), self._relief),
            dependencies.require(PlanSlot(SurfacePlanSlot.RIVER_RELIEF.value), self._river_relief),
            dependencies.require(PlanSlot(SurfacePlanSlot.HYDROLOGY.value), self._hydrology),
            dependencies.require(PlanSlot(SurfacePlanSlot.CLIMATE_LOCAL.value), self._climate_local))
        cells = shore_cells(dep.hydrology.payload, request.inputs.grid.fine_span)
        # Unit spans are joined using the common interval owner.
        from app.application.worldData.generators.terrain.regions.coverageMeasure import normalized_spans
        coverage = RegionCoverage(region_uid=request.key.world_uid, spans=normalized_spans(
            CoverageSpan(y=y, x0=x, x1=FineX(x + 1)) for x, y in sorted(cells, key=lambda c: (c[1], c[0]))))
        facts = self.facts(request, dep, cells=coverage)
        control.raise_if_shutdown()
        return PlanBuildResult[SurfaceSupportPlan](payload=SurfaceSupportPlan(facts=facts), diagnostics=())


class CoatingPlanProvider:
    def __init__(self, support: RegisteredPlanContract[SurfaceSupportInput, SurfaceSupportPlan],
                 hydrology: RegisteredPlanContract[HydrologyFinalInput, HydrologyPlan], *, fine_span: int):
        if fine_span <= 0:
            raise ValueError("coating requires positive fine span")
        self._support, self._hydrology, self._span = support, hydrology, fine_span

    @staticmethod
    def plan(inputs: CoatingPlanInput, support: SurfaceSupportPlan,
             hydrology: HydrologyPlan, *, fine_span: int) -> PlanBuildResult[CoatingPlan]:
        spec = compile_value_policy(SURFACE_COATING_POLICY, (
            SurfaceCoatingSelection, SurfaceCoatingFacts, SurfaceCoatingTargetFacts))
        selection = SurfaceCoatingSelection(action=SurfaceCoatingAction.APPLY_SHORE_SURFACE)
        source = PolicyInputs((PolicySource(SurfaceCoatingSelection, selection, ("coating",)),))
        shores = shore_cells(hydrology, fine_span)
        if fine_span <= 0 or set(shores) - {f.cell for f in support.facts}:
            raise ValueError("coating requires support evidence for every final shore cell")
        targets = dict(inputs.targets)
        cells: list[CoatingCellPlan] = []
        diagnostics: list[PlanDiagnostic] = []
        resolver = PolicyResolver()
        for facts in support.facts:
            shore = shores.get(facts.cell)
            if shore is None:
                continue
            target = targets.get(shore.shore_kind, inputs.default_target) if shore.shore_kind is not None else inputs.default_target
            observations = PolicyFacts((PolicySource(SurfaceCoatingFacts, facts, ("surface_support", *facts.cell)),
                PolicySource(SurfaceCoatingTargetFacts, SurfaceCoatingTargetFacts(target=target), ("coating", *facts.cell))))
            decision = resolver.resolve(spec, source, observations, mode=inputs.resolution_mode)
            cells.append(CoatingCellPlan(cell=facts.cell, face=facts.face, decision=decision,
                target=target.value if decision.behavior is SurfaceCoatingAction.APPLY_SHORE_SURFACE and isinstance(target, KnownFact) else None))
            disposition = PlanDiagnosticDisposition.ERROR if inputs.resolution_mode is ResolutionMode.VALIDATE_ONLY else PlanDiagnosticDisposition.FALLBACK
            diagnostics.extend(PlanDiagnostic(issue=i, disposition=disposition) for i in decision.issues)
        return PlanBuildResult[CoatingPlan](payload=CoatingPlan(cells=tuple(cells)), diagnostics=tuple(dict.fromkeys(diagnostics)))

    def build(self, request: PlanRequest[CoatingPlanInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[CoatingPlan]:
        control.raise_if_shutdown()
        support = dependencies.require(SURFACE_SUPPORT_SLOT, self._support)
        hydro = dependencies.require(PlanSlot(SurfacePlanSlot.HYDROLOGY.value), self._hydrology)
        for envelope in (support, hydro):
            if envelope.ref.key.world_uid != request.key.world_uid or envelope.ref.key.scope != request.key.scope:
                raise ValueError("coating requires same-world/scope evidence")
        if any(f.world_uid != support.ref.key.world_uid or
               f.support_input_fingerprint != support.ref.key.input_fingerprint for f in support.payload.facts):
            raise ValueError("support facts do not match their captured input revision")
        if not any(d.ref == hydro.ref and d.slot == SurfacePlanSlot.HYDROLOGY.value for d in support.dependencies):
            raise ValueError("coating support and final hydrology revisions differ")
        result = self.plan(request.inputs, support.payload, hydro.payload, fine_span=self._span)
        control.raise_if_shutdown()
        return result
