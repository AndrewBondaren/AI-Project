"""Natural mountain layout and light recipe, independent of basin placement."""

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.application.worldData.generators.terrain.mountains.collect import collect_prepared_mountain_entries_for_coarse
from app.application.worldData.generators.terrain.mountains.formPipeline import materialize_mountain_entry
from app.application.worldData.generators.terrain.mountains.peakAssembler import assemble_peak_from_policy
from app.application.worldData.generators.terrain.mountains.reliefSidesStamp import stamp_prepared_entry
from app.application.worldData.generators.terrain.noise import cell_z_noise
from app.application.worldData.generators.terrain.reliefObjects.depressionDetect import detect_depression_cells
from app.application.worldData.generators.terrain.reliefObjects.elevationResolve import resolve_mountain_surface_z, resolve_ravine_surface_z
from app.application.worldData.generators.coordinates.light.grid import light_cell_center_fine
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.registryKey import RegistryKey
from app.dataModel.spatial.facing import Facing
from app.dataModel.spatial.grid.coordinateTypes import FineZ, GridX, GridY, LightCellRef
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput
from app.dataModel.terrain.relief.planning.reliefPlan import LightMountainCell, LightRavineCell, LightReliefPlan, MountainLayout, light_order
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def mountain_layout(inputs: ReliefPlanInput, terrain: TerrainPlan, climate: ClimateBasePlan,
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


def light_relief(inputs: ReliefPlanInput, terrain: TerrainPlan, layout: MountainLayout,
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


