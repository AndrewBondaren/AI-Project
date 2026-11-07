"""One final multi-source fill: cells agree with the resolved effective levels."""

from collections.abc import Callable, Mapping
from app.dataModel.hydrology.planning.stages.openWaterPlan import MaterializedWater

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.hydrology.water.componentLabel import component_fills
from app.application.worldData.generators.hydrology.water.levelFill import LevelFillSource, labelled_level_fill
from app.application.worldData.generators.hydrology.water.shoreDerive import derive_shore
from app.application.worldData.generators.hydrology.water.waterBodyResolver import ResolvedWaterLevels
from app.application.worldData.generators.hydrology.water.waterClassifier import classify_components
from app.dataModel.hydrology import waterDiagnostics as wd
from app.application.worldData.generators.hydrology.water.waterSources import WaterSource
from app.application.worldData.generators.hydrology.waterBodyIdentity import AutoWaterBodyRole, auto_water_body_uid
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.distanceField import distance_from_boundary
from app.dataModel.hydrology.waterKindMismatchIssue import WaterKindMismatchIssue
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.dataModel.planning.diagnostics.planDiagnostic import DiagnosticCarrier, PlanDiagnostic, PlanDiagnosticDisposition


def materialize_water(surface_z: Mapping[Coord, int], sources: tuple[WaterSource, ...],
                      resolved: ResolvedWaterLevels, topology: WorldTopology,
                      policy: WorldHydrology, ctx: ResolveContext,
                      allowed_kinds: frozenset[BasinKind] | None = None, *,
                      emit: Callable[[DiagnosticCarrier], None]) -> MaterializedWater:
    fill = labelled_level_fill(surface_z, tuple(
        LevelFillSource(i, source.spec.source_uid, source.seeds, resolved.levels[i])
        for i, source in enumerate(sources)
    ), topology)
    owners = fill.owners

    fills = component_fills(owners, topology, surface_z)
    components = tuple(fill.cells for fill in fills)
    levels = []
    for component in components:
        component_levels = {resolved.levels[owners[cell]] for cell in component}
        if len(component_levels) != 1:
            raise ValueError("physical water contact has unresolved differing levels")
        levels.append(component_levels.pop())
    kinds = classify_components(fills, levels, topology, policy.default_water_level,
                                 policy.default_seas, [None] * len(fills))
    wet = set()
    kinds_by_source = {}
    auto_remap = {}
    for component, kind in zip(components, kinds):
        indices = {owners[cell] for cell in component}
        authored = {i for i in indices if sources[i].authored}
        if not authored and allowed_kinds is not None and kind not in allowed_kinds:
            continue
        lake_category = (all(sources[i].spec.kind is BasinKind.LAKE for i in authored)
                         if authored else kind is BasinKind.LAKE)
        minimum = (policy.default_lakes.min_water_cells if lake_category
                   else policy.default_seas.min_water_cells)
        if len(component) < minimum:
            anchor = min(component, key=lambda cell: (cell[1], cell[0]))
            emit(wd.WaterPuddleDiagnostic(
                issue=wd.WaterPuddle(code=wd.WaterDiagnosticCode.WATER_PUDDLE,
                    source_uid=sources[owners[anchor]].spec.source_uid, cell_count=len(component), minimum_cells=minimum),
                disposition=PlanDiagnosticDisposition.ERROR,
            ))
            continue
        wet.update(component)
        anchor = min(component, key=lambda cell: (cell[1], cell[0]))
        auto_uid = auto_water_body_uid(AutoWaterBodyRole.LAKE if kind is BasinKind.LAKE
                                       else AutoWaterBodyRole.SEA, anchor)
        for i in indices:
            kinds_by_source[i] = sources[i].spec.kind if sources[i].authored else kind
            if not sources[i].authored:
                auto_remap[sources[i].spec.source_uid] = auto_uid
        for i in authored:
            if sources[i].spec.kind is not kind:
                spec = sources[i].spec
                issue = WaterKindMismatchIssue.retained(spec.source_uid, spec.kind, kind)
                emit(PlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.FALLBACK))
    distances = distance_from_boundary(frozenset(wet), topology)
    by_cell, areas, floors = {}, {}, {}
    bodies: dict[str, WaterBody] = {}
    for cell in sorted(wet, key=lambda c: (c[1], c[0])):
        i = owners[cell]
        source, level = sources[i], resolved.levels[i]
        spec, kind = source.spec, kinds_by_source[i]
        uid = auto_remap.get(spec.source_uid, spec.source_uid)
        distance = distances.get(cell, spec.bands.max + 1)
        role = {
            BasinKind.LAKE: HydrologyCellRole.LAKE,
            BasinKind.INLAND_SEA: HydrologyCellRole.INLAND_SEA,
            BasinKind.SEA: HydrologyCellRole.COASTAL_SEA,
            BasinKind.OCEAN: (HydrologyCellRole.OPEN_OCEAN if distance > spec.bands.max
                              else HydrologyCellRole.COASTAL_SEA),
        }[kind]
        by_cell[cell] = MapCellHydrology(role=role, water_body_uid=uid,
                                         z_water_level=level, deepening_index=distance)
        areas[uid] = areas.get(uid, 0) + 1
        floor = spec.floor_z if source.authored else surface_z[cell]
        floors[uid] = min(floors.get(uid, floor), floor)
        if uid not in bodies:
            bodies[uid] = WaterBody(
                water_body_uid=uid, location_uid=spec.source_uid if source.authored else None,
                kind=kind, liquid=spec.liquid, declared_level=resolved.declared_levels[i],
                z_water_level=level, declared_basin_uid=spec.source_uid if source.authored else None,
                parent_system_uid=resolved.parents[i] if source.authored else None,
            )
    spills = {spill.source_uid: spill for spill in resolved.spills}
    for i, source in enumerate(sources):
        uid = source.spec.source_uid
        # Coincident declarations retain their distinct object identities even
        # when the single-owner cell index allocates all tied cells to one UID.
        if source.authored and uid not in bodies:
            wet_seed = next((cell for cell in source.seeds if cell in wet
                             and surface_z[cell] < resolved.levels[i]), None)
            if wet_seed is not None:
                bodies[uid] = WaterBody(
                    water_body_uid=uid, location_uid=uid, kind=source.spec.kind,
                    liquid=source.spec.liquid, declared_level=resolved.declared_levels[i],
                    z_water_level=resolved.levels[i], declared_basin_uid=uid,
                    parent_system_uid=resolved.parents[i],
                )
                areas[uid], floors[uid] = 0, source.spec.floor_z
        if source.authored and not any(surface_z[cell] < resolved.levels[i] for cell in source.seeds):
            emit(wd.WaterCannotHoldDiagnostic(
                issue=wd.WaterCannotHold(code=wd.WaterDiagnosticCode.WATER_CANNOT_HOLD,
                    source_uid=uid, effective_level=resolved.levels[i]),
                disposition=PlanDiagnosticDisposition.ERROR,
            ))
        if source.authored and uid in spills:
            emit(wd.WaterLevelSpillDiagnostic(issue=spills[uid], disposition=PlanDiagnosticDisposition.FALLBACK))
        if source.authored and resolved.declared_levels[i] != resolved.levels[i]:
            emit(wd.WaterLevelSupersededDiagnostic(
                issue=wd.WaterLevelSuperseded(code=wd.WaterDiagnosticCode.WATER_LEVEL_SUPERSEDED,
                    source_uid=uid, declared_level=resolved.declared_levels[i],
                    effective_level=resolved.levels[i], parent_system_uid=resolved.parents[i]),
                disposition=PlanDiagnosticDisposition.FALLBACK,
            ))
    by_cell.update(derive_shore(surface_z, by_cell, topology))
    mapping = SourceBodyMapping(entries=tuple(SourceBodyMappingEntry(source_uid=source.spec.source_uid,
        body_uids=tuple(sorted({cell.water_body_uid for coord in source.spec.footprint
            if (cell := by_cell.get(coord)) is not None and cell.liquid_candidate
            and cell.water_body_uid is not None})))
        for source in sorted(sources, key=lambda source: source.spec.source_uid) if source.authored))
    return MaterializedWater(tuple((cell, by_cell[cell]) for cell in sorted(by_cell, key=lambda c: (c[1], c[0]))),
        tuple(bodies[uid] for uid in sorted(bodies)), tuple(sorted(areas.items())),
        tuple(sorted(floors.items())), tuple(sorted(auto_remap.items())), mapping)
