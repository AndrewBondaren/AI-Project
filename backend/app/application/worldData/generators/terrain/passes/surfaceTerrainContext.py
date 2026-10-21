"""Shared coarse + hydrology planning for fine-tile materialization."""

from __future__ import annotations

from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.coordinates.convert import map_cell_fine_span
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.dataModel.topology.fineTopology import fine_topology

from dataclasses import dataclass
from app.application.jsonValidation.resolve import ResolveContext
from app.dataModel.hydrology.waterBody import WaterBody

from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.hydrology.placement import (
    run_water_placement_pass,
)
from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import (
    apply_declared_fine_river_carves,
)
from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass_coarse
from app.application.worldData.generators.terrain.reliefObjects import apply_relief_objects_z
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.climate.localFieldFromCoarse import (
    build_local_field_from_coarse,
)
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass(frozen=True)
class SurfaceTerrainContext:
    pole_field: ClimatePoleField
    local_field: ClimateAnchorField
    coarse_hm: SurfaceHeightmap
    coarse_hydro: dict[tuple[int, int], MapCellHydrology]
    sparse_fine_hydro: dict[tuple[int, int], MapCellHydrology]
    fine_z_overrides: dict[tuple[int, int], int]
    # Pre-1.4 macro z (relief only) — light ReliefContributor base. Not hydro SoT.
    coarse_relief_z: dict[tuple[int, int], int]
    # Post-1.4 (+ hydro carve) macro z — hydro / fine upsample SoT.
    # Fine-cell overrides live in fine_z_overrides.
    coarse_surface_z: dict[tuple[int, int], int]


def require_surface_terrain_context(
    world: World,
    locations: list[NamedLocation],
    *,
    nodes: list[ConnectionNode] | None = None,
    edges: list[ConnectionEdge] | None = None,
    hydrology_generator: HydrologyGeneratorService | None = None,
    resolve_ctx: ResolveContext | None = None,
) -> SurfaceTerrainContext:
    """Fail-closed planning for pack bake / refine HTTP and orchestrators."""
    ctx = prepare_surface_terrain_context(
        world,
        locations,
        nodes=nodes,
        edges=edges,
        hydrology_generator=hydrology_generator,
        resolve_ctx=resolve_ctx,
    )
    if ctx is None:
        raise ValueError("surface terrain context unavailable")
    return ctx


def prepare_surface_terrain_context(
    world: World,
    locations: list[NamedLocation],
    *,
    nodes: list[ConnectionNode] | None = None,
    edges: list[ConnectionEdge] | None = None,
    hydrology_generator: HydrologyGeneratorService | None = None,
    resolve_ctx: ResolveContext | None = None,
) -> SurfaceTerrainContext | None:
    pole_field = run_pole_resolve_pass(world, locations)
    coarse_hm = run_surface_pass_coarse(world, locations, pole_field)
    if coarse_hm is None:
        return None

    # Pre-1.4 snapshot for light relief (avoid double-rise when mountain raises on light).
    coarse_relief_z = dict(coarse_hm.surface_z)

    water = run_water_placement_pass(world, locations, coarse_hm)

    topology = water.topology if water is not None else resolve_hydrology_topology(
        world, coarse_hm, locations=locations)

    # Pass 1.4 — mountain rise / ravine drop before hydrology detect (1.5).
    apply_relief_objects_z(
        world, locations, coarse_hm, pole_field=pole_field,
        basin_specs=water.basin_specs if water else (),
        topology=topology,
    )

    # Fine profiles sample the same pre-river snapshot, avoiding a second bed cut.
    pre_river_z = dict(coarse_hm.surface_z)
    coarse_hydro: dict[tuple[int, int], MapCellHydrology] = {}
    water_bodies: tuple[WaterBody, ...] = ()
    if is_hydrology_enabled(world):
        hydro = hydrology_generator or HydrologyGeneratorService()
        hydro_result = hydro.apply(
            world,
            locations,
            coarse_hm,
            nodes=nodes or [],
            edges=edges or [],
            basin_specs=water.basin_specs if water else (),
            topology=topology,
            ctx=resolve_ctx,
        )
        coarse_hydro = hydro_result.cell_index.by_cell
        water_bodies = hydro_result.water_bodies

    sparse_fine_hydro, fine_z_overrides = apply_declared_fine_river_carves(
        world,
        locations,
        pre_river_z,
        topology=fine_topology(topology, map_cell_fine_span(world)),
        base_space=CoordinateSpace.WORLD_SURFACE_GRID,
        coarse_hydro=coarse_hydro,
        water_bodies=water_bodies,
        ctx=resolve_ctx,
    )
    local_field = build_local_field_from_coarse(world, locations, pole_field, coarse_hm)

    return SurfaceTerrainContext(
        pole_field=pole_field,
        local_field=local_field,
        coarse_hm=coarse_hm,
        coarse_hydro=coarse_hydro,
        sparse_fine_hydro=sparse_fine_hydro,
        fine_z_overrides=fine_z_overrides,
        coarse_relief_z=coarse_relief_z,
        coarse_surface_z=dict(coarse_hm.surface_z),
    )
