"""River channel carve on declare polylines вЂ” D HY-4, U24/U28."""

from __future__ import annotations

from dataclasses import dataclass, replace
from app.dataModel.topology.worldTopology import WorldTopology
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.application.worldData.generators.hydrology.rivers.riverBedCarver import _channel_depth_step, river_bed_spec, river_bed_roles
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec, apply_river_bed_z
from app.application.worldData.generators.hydrology.waterfalls.riverDrops import river_drop_facts
from app.dataModel.hydrology.waterfallDrop import WaterfallDrop
from typing import Any

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import (
    segments_from_declared,
)
from app.application.worldData.generators.hydrology.load.hydrologyAutoresolvePolicy import (
    rivers_autoresolve_policy,
)
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.hydrology.types import (
    HydrologyMasterInput,
    RiverSegment,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


@dataclass(frozen=True)
class AssembledRivers:
    by_cell: dict[tuple[int, int], MapCellHydrology]
    segments: list[RiverSegment]
    dirty_bbox: GridBBox | None
    bed_specs: tuple[RiverBedSpec, ...]
    drops: tuple[WaterfallDrop, ...]


def assemble_rivers(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
    occupied: dict[tuple[int, int], MapCellHydrology] | None = None,
    locations: list[Any] | None = None,
    *, topology: WorldTopology | None = None,
) -> AssembledRivers:
    topology = topology or resolve_hydrology_topology(world, heightmap, locations=locations)
    type_classify = resolve_river_type_classify(world)
    river_segments = segments_from_declared(master.declared_river_edges, topology=topology)
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    xs: list[int] = []
    ys: list[int] = []
    occupied_cells = dict(occupied or {})

    if master.declared_river_intents and locations is not None:
        from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import (
            resolve_declared_river_intents,
        )

        for segment in resolve_declared_river_intents(
            world,
            heightmap,
            master.declared_river_intents,
            locations,
            occupied_cells,
            type_classify,
            space=CoordinateSpace.WORLD_SURFACE_GRID, topology=topology,
        ):
            river_segments.append(segment)

    # Reserve declared beds while planning all paths on the same pre-bed snapshot.
    z_min = world_z_min(world)
    specs = []
    accepted = []
    drops = []

    def prepare(segment):
        cells = []
        for cell in segment.polyline_cells:
            if cell not in heightmap.surface_z:
                continue
            cells.append(cell)
            if is_river_mouth(cell, heightmap.surface_z, occupied_cells):
                break
        segment = replace(segment, polyline_cells=cells)
        spec = river_bed_spec(heightmap, segment,
                              depth_step=_channel_depth_step(segment.connection_type, type_classify),
                              z_min=z_min, occupied=occupied_cells)
        if not spec.bed_z:
            return
        accepted.append(segment)
        specs.append(spec)
        merged.update(river_bed_roles(segment, spec))
        drops.extend(river_drop_facts(heightmap, segment, spec, occupied_cells))

    for segment in river_segments:
        prepare(segment)
    rivers_policy = rivers_autoresolve_policy(world)
    if rivers_policy.rivers_enabled and rivers_policy.autoresolve:
        from app.application.worldData.generators.hydrology.autoresolve.proceduralRiverAutoresolve import autoresolve_river_segments
        for segment in autoresolve_river_segments(world, heightmap, master,
                                                   {**occupied_cells, **merged}, topology=topology):
            if not any(cell in merged for cell in segment.polyline_cells[:-1]):
                prepare(segment)
    apply_river_bed_z(heightmap, specs)
    for cell in merged:
        xs.append(cell[0])
        ys.append(cell[1])

    dirty = None
    if xs and ys:
        dirty = GridBBox(min(xs), max(xs), min(ys), max(ys))
    return AssembledRivers(merged, accepted, dirty, tuple(specs), tuple(drops))


def generate_rivers(*args, **kwargs):
    result = assemble_rivers(*args, **kwargs)
    return result.by_cell, result.segments, result.dirty_bbox
