"""One mountain layout, coarse pre-river heights and full-extent light projections."""

from collections.abc import Callable
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.application.worldData.generators.terrain.mountains.collect import collect_prepared_mountain_entries_for_coarse
from app.application.worldData.generators.terrain.mountains.formPipeline import (
    coarse_footprint_for_entry, materialize_mountain_entry,
)
from app.application.worldData.generators.terrain.mountains.peakAssembler import assemble_peak_from_policy
from app.application.worldData.generators.terrain.mountains.reliefSidesStamp import stamp_prepared_entry
from app.application.worldData.generators.terrain.noise import cell_z_noise
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import apply_basin_z
from app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedZ import river_bed_spec, apply_river_bed_z
from app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedSpec import RiverBedSpec
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.reliefObjects.depressionDetect import detect_depression_cells
from app.application.worldData.generators.terrain.reliefObjects.elevationResolve import (
    resolve_mountain_surface_z, resolve_ravine_surface_z,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale, light_cell_center_fine
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.registryKey import RegistryKey
from app.dataModel.spatial.facing import Facing
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineXY, FineZ, GridX, GridY, LightCellRef, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import (
    LightMountainCell, LightRavineCell, LightReliefPlan, MountainLayout, ReliefPlan, light_order,
    RiverReliefPlan, RiverBedRecord,
)
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyRoutesPlan, RiverRoute
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.mountain.enums import MountainKind
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _mountain_layout(inputs: ReliefPlanInput, terrain: TerrainPlan, climate: ClimateBasePlan,
                     world_uid: str, ctx: ResolveContext, control: PlanBuildControl) -> MountainLayout:
    entries: list[MountainSpec | MountainRangeSpec] = []
    if inputs.masks_enabled and inputs.mountains.enabled:
        anchors = [assemble_peak_from_policy(origin_x_m=anchor.position[0], origin_y_m=anchor.position[1],
            policy=inputs.mountains, location_uid=anchor.location_uid) for anchor in inputs.anchors]

        def typical(ox: int, oy: int) -> int:
            return ClimatePlanSampler.sample(climate, GridX(ox // inputs.grid.fine_span),
                GridY(oy // inputs.grid.fine_span)).typical_elevation_z

        selected = collect_prepared_mountain_entries_for_coarse(seed=inputs.seed, policy=inputs.mountains,
            declared=list(inputs.declared_mountains), anchors=anchors,
            heightmap_keys=((coord.gx, coord.gy) for coord, _ in terrain.surface_z),
            cell_m=inputs.grid.fine_span, typical_of=typical)
        templates = {template.template_uid: template for template in inputs.mountain_templates}
        for index, entry in enumerate(selected):
            control.raise_if_shutdown()
            try:
                entries.append(stamp_prepared_entry(entry, world_policy=inputs.mountain_pick,
                    world_seed=world_uid, templates_by_uid=templates,
                    resolve_ctx=ctx.child("mountain_layout").child(index)))
            except UnresolvedModelError:
                # The shared picker collected the error; this object has no height effects.
                continue
    return MountainLayout(entries=tuple(entries), templates=inputs.mountain_templates,
        world_pick=inputs.mountain_pick,
        terrain_key=RegistryKey[WorldTerrainRegistry](inputs.mountains.system_terrain))


def _coarse_relief(inputs: ReliefPlanInput, terrain: TerrainPlan, water: WaterPlacementPlan,
                   layout: MountainLayout, world_uid: str, scale: LightGridScale,
                   control: PlanBuildControl) -> tuple[tuple[SurfaceGridCoord, FineZ], ...]:
    surface: dict[tuple[int, int], int] = {(coord.gx, coord.gy): z for coord, z in terrain.surface_z}
    fractions: dict[tuple[int, int], float] = {}
    kinds: dict[tuple[int, int], MountainKind] = {}
    for entry in layout.entries:
        control.raise_if_shutdown()
        footprint = coarse_footprint_for_entry(entry, cell_m=inputs.grid.fine_span, light_span=float(scale.light_span))
        for cell, fraction in footprint.items():
            if cell in surface and (cell not in fractions or fraction > fractions[cell]):
                fractions[cell], kinds[cell] = fraction, entry.kind
    for cell, fraction in fractions.items():
        surface[cell] = resolve_mountain_surface_z(surface[cell], z_min=inputs.z_min, z_max=inputs.z_max,
            kind=kinds[cell], side_fraction=fraction)
    if inputs.masks_enabled and inputs.ravines.enabled and inputs.ravines.autoresolve:
        for cell in detect_depression_cells(surface, inputs.ravines):
            surface[cell] = resolve_ravine_surface_z(surface[cell], z_min=inputs.z_min, policy=inputs.ravines)
    heightmap = SurfaceHeightmap(world_uid=world_uid, bbox=terrain.bbox, surface_z=surface)
    apply_basin_z(heightmap, water.basin_specs, water.topology, reserved=frozenset(fractions), grid=inputs.grid)
    return tuple((coord, FineZ(surface[(coord.gx, coord.gy)])) for coord, _ in terrain.surface_z)


def _light_relief(inputs: ReliefPlanInput, terrain: TerrainPlan, layout: MountainLayout,
                  scale: LightGridScale, control: PlanBuildControl) -> LightReliefPlan:
    coarse: dict[tuple[int, int], int] = {(coord.gx, coord.gy): z for coord, z in terrain.surface_z}
    base: dict[LightCellRef, int] = {}
    for coord, _ in terrain.surface_z:
        control.raise_if_shutdown()
        for ty in range(scale.side):
            for tx in range(scale.side):
                x, y = light_cell_center_fine(coord.gx, coord.gy, tx, ty, scale)
                macro = (x // inputs.grid.fine_span, y // inputs.grid.fine_span)
                if macro not in coarse:
                    raise PlanBuildFailure((FieldPathError(("grid",), "light grid center outside terrain extent"),))
                z = cell_z_noise(inputs.seed, x, y, coarse[macro])
                base[LightCellRef(coord.gx, coord.gy, tx, ty)] = max(inputs.z_min, min(inputs.z_max, z))
    mountains: dict[LightCellRef, LightMountainCell] = {}
    for entry in layout.entries:
        control.raise_if_shutdown()
        footprint = materialize_mountain_entry(entry, scale)
        for cell in footprint.cells:
            if cell not in base:
                continue
            previous = mountains.get(cell)
            z = resolve_mountain_surface_z(base[cell], z_min=inputs.z_min, z_max=inputs.z_max,
                kind=entry.kind, side_fraction=footprint.elevation_fraction.get(cell, 1.0))
            face = footprint.system_facing.get(cell)
            facing = Facing(face) if face is not None else previous.facing if previous else None
            mountains[cell] = LightMountainCell(cell=cell,
                surface_z=FineZ(max(previous.surface_z if previous else base[cell], z)), facing=facing)
    ravines: dict[LightCellRef, LightRavineCell] = {}
    if inputs.masks_enabled and inputs.ravines.enabled and inputs.ravines.autoresolve:
        refs = {(cell.gx * scale.side + cell.tx, cell.gy * scale.side + cell.ty): cell for cell in base}
        surface = {absolute: mountains[cell].surface_z if cell in mountains else base[cell]
                   for absolute, cell in refs.items()}
        for absolute in detect_depression_cells(surface, inputs.ravines):
            cell = refs[absolute]
            ravines[cell] = LightRavineCell(cell=cell, surface_z=FineZ(resolve_ravine_surface_z(
                surface[absolute], z_min=inputs.z_min, policy=inputs.ravines)))
    return LightReliefPlan(base_surface_z=tuple((cell, FineZ(z)) for cell, z in base.items()),
        mountain_cells=tuple(mountains[cell] for cell in sorted(mountains, key=light_order)),
        ravine_cells=tuple(ravines[cell] for cell in sorted(ravines, key=light_order)),
        ravine_terrain=RegistryKey[WorldTerrainRegistry](inputs.ravines.system_terrain), terrain_merge=inputs.terrain_merge)


class ReliefPlanProvider:
    def __init__(self, climate_base: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan],
                 terrain_base: RegisteredPlanContract[TerrainBaseInput, TerrainPlan],
                 water_placement: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan]) -> None:
        self._climate, self._terrain, self._water = climate_base, terrain_base, water_placement

    def build(self, request: PlanRequest[ReliefPlanInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[ReliefPlan]:
        control.raise_if_shutdown()
        climate = dependencies.require(PlanSlot(SurfacePlanSlot.CLIMATE_BASE.value), self._climate)
        terrain = dependencies.require(PlanSlot(SurfacePlanSlot.TERRAIN_BASE.value), self._terrain)
        water = dependencies.require(PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value), self._water)
        terrain_refs = {dependency.slot: dependency.ref for dependency in terrain.dependencies}
        water_refs = {dependency.slot: dependency.ref for dependency in water.dependencies}
        if (terrain_refs.get(PlanSlot(SurfacePlanSlot.CLIMATE_BASE.value)) != climate.ref
                or water_refs.get(PlanSlot(SurfacePlanSlot.TERRAIN_BASE.value)) != terrain.ref):
            raise PlanBuildFailure((FieldPathError(("dependencies",), "incoherent upstream climate/terrain/water refs"),))
        inputs, base = request.inputs, terrain.payload
        bounds = water.payload.topology.bounds
        if ((base.bbox.x_min, base.bbox.x_max, base.bbox.y_min, base.bbox.y_max)
                != (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max)
                or any(not inputs.z_min <= z <= inputs.z_max for _, z in base.surface_z)):
            raise PlanBuildFailure((FieldPathError((SurfacePlanSlot.TERRAIN_BASE.value,),
                "relief requires coherent terrain extent and world z bounds"),))
        if any(not inputs.z_min <= spec.floor_z < spec.z_water_level <= inputs.z_max
               for spec in water.payload.basin_specs):
            raise PlanBuildFailure((FieldPathError((SurfacePlanSlot.WATER_PLACEMENT.value,),
                "basin levels outside relief world z bounds"),))
        ctx = ResolveContext(collect_only=True)
        layout = _mountain_layout(inputs, base, climate.payload, request.key.world_uid, ctx, control)
        scale = LightGridScale.from_tile(inputs.grid.fine_span, inputs.grid.light_side)
        surface = _coarse_relief(inputs, base, water.payload, layout, request.key.world_uid, scale, control)
        light = _light_relief(inputs, base, layout, scale, control)
        control.raise_if_shutdown()
        return PlanBuildResult[ReliefPlan](payload=ReliefPlan(surface_z=surface, mountain_layout=layout, light=light),
            diagnostics=tuple(PlanDiagnostic(issue=issue, disposition=PlanDiagnosticDisposition.ERROR)
                              for issue in dict.fromkeys(ctx.errors)))


def _river_beds[S](routes: tuple[RiverRoute[S], ...], base: tuple[tuple[S, FineZ], ...], *,
                   topology: WorldTopology, world_uid: str, z_min: int,
                   depths: dict[HydrologyConnectionType, int], to_xy: Callable[[S], Coord],
                   from_xy: Callable[[Coord], S], control: PlanBuildControl,
                   ) -> tuple[tuple[tuple[S, FineZ], ...], tuple[RiverBedRecord[S], ...]]:
    bounds = topology.bounds
    surface = {to_xy(cell): int(z) for cell, z in base}
    snapshot = SurfaceHeightmap(world_uid=world_uid,
        bbox=GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max), surface_z=surface)
    specs: list[RiverBedSpec] = []
    cells_by_river: dict[str, set[Coord]] = {}
    for route in routes:
        control.raise_if_shutdown()
        receiver = to_xy(route.receiver_cell)
        targets: set[Coord] = set()
        for segment in route.segments:
            path = [to_xy(cell) for cell in segment.path]
            if any(cell not in surface or topology.canonicalize(*cell) != cell for cell in path):
                raise PlanBuildFailure((FieldPathError((SurfacePlanSlot.HYDROLOGY_ROUTES.value, route.river_uid),
                    "river path/receiver requires canonical pre-river heights"),))
            prepared = RiverSegment(polyline_cells=path, connection_type=segment.connection_type.value,
                edge_uid=segment.edge_uid, location_uid=segment.location_uid, declared=segment.declared)
            spec = river_bed_spec(snapshot, prepared, depth_step=depths[segment.connection_type],
                z_min=z_min, occupied={}, receiver_cell=receiver)
            specs.append(spec)
            targets.update(cell for cell, _ in spec.bed_z)
        if not targets:
            raise PlanBuildFailure((FieldPathError((SurfacePlanSlot.HYDROLOGY_ROUTES.value, route.river_uid),
                "accepted river requires nonempty land-bed cells"),))
        cells_by_river[route.river_uid] = targets
    # A tributary's receiver may be part of its parent river's bed. That parent
    # writes it; the tributary's own spec still excludes its terminal receiver.
    apply_river_bed_z(snapshot, specs)
    return (tuple((cell, FineZ(surface[to_xy(cell)])) for cell, _ in base),
        tuple(RiverBedRecord[S](river_uid=route.river_uid, bed_z=tuple(
            (from_xy(cell), FineZ(surface[cell])) for cell in sorted(cells_by_river[route.river_uid], key=lambda cell: (cell[1], cell[0]))))
            for route in routes))


class RiverReliefPlanProvider:
    def __init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
                 hydrology_routes: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan]) -> None:
        self._relief, self._routes = relief, hydrology_routes

    def build(self, request: PlanRequest[RiverReliefInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[RiverReliefPlan]:
        control.raise_if_shutdown()
        relief = dependencies.require(PlanSlot(SurfacePlanSlot.RELIEF.value), self._relief)
        routes = dependencies.require(PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value), self._routes)
        refs = {dependency.slot: dependency.ref for dependency in routes.dependencies}
        if refs.get(PlanSlot(SurfacePlanSlot.RELIEF.value)) != relief.ref:
            raise PlanBuildFailure((FieldPathError(("dependencies",), "routes must use the exact pre-river relief ref"),))
        inputs = request.inputs
        bounds = inputs.topology.bounds
        coarse = relief.payload.surface_z
        if (len(coarse) != bounds.width * bounds.height or any(
                inputs.topology.canonicalize(cell.gx, cell.gy) != (cell.gx, cell.gy) for cell, _ in coarse)):
            raise PlanBuildFailure((FieldPathError((SurfacePlanSlot.RELIEF.value,), "river relief requires complete coarse extent"),))
        surface, beds = _river_beds(routes.payload.coarse_routes, coarse, topology=inputs.topology,
            world_uid=request.key.world_uid, z_min=inputs.z_min, depths=dict(inputs.channel_depths),
            to_xy=lambda cell: (cell.gx, cell.gy), from_xy=lambda cell: SurfaceGridCoord(GridX(cell[0]), GridY(cell[1])),
            control=control)
        fine_surface, fine_beds = _river_beds(routes.payload.fine_routes, routes.payload.fine_base_surface_z,
            topology=fine_topology(inputs.topology, inputs.grid.fine_span), world_uid=request.key.world_uid,
            z_min=inputs.z_min, depths=dict(inputs.channel_depths), to_xy=lambda cell: cell,
            from_xy=lambda cell: (FineX(cell[0]), FineY(cell[1])), control=control)
        control.raise_if_shutdown()
        return PlanBuildResult[RiverReliefPlan](payload=RiverReliefPlan(surface_z=surface, fine_surface_z=fine_surface,
            coarse_beds=beds, fine_beds=fine_beds), diagnostics=())
