"""Shared coarse + hydrology planning for fine-tile materialization."""

from __future__ import annotations

from dataclasses import dataclass

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
from app.application.worldData.generators.hydrology.shore.meterHydrologyIndex import (
    apply_declared_meter_river_carves,
)
from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass_coarse
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
    coarse_hydro: dict[tuple[int, int], object]
    sparse_meter_hydro: dict[tuple[int, int], MapCellHydrology]
    meter_z_overrides: dict[tuple[int, int], int]
    # Macro-grid keys only: (gx, gy) → surface z. Meter overrides live in meter_z_overrides.
    coarse_surface_z: dict[tuple[int, int], int]


def require_surface_terrain_context(
    world: World,
    locations: list[NamedLocation],
    *,
    nodes: list[ConnectionNode] | None = None,
    edges: list[ConnectionEdge] | None = None,
    hydrology_generator: HydrologyGeneratorService | None = None,
) -> SurfaceTerrainContext:
    """Fail-closed planning for pack bake / refine HTTP and orchestrators."""
    ctx = prepare_surface_terrain_context(
        world,
        locations,
        nodes=nodes,
        edges=edges,
        hydrology_generator=hydrology_generator,
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
) -> SurfaceTerrainContext | None:
    pole_field = run_pole_resolve_pass(world, locations)
    coarse_hm = run_surface_pass_coarse(world, locations, pole_field)
    if coarse_hm is None:
        return None

    coarse_hydro: dict[tuple[int, int], object] = {}
    if is_hydrology_enabled(world):
        hydro = hydrology_generator or HydrologyGeneratorService()
        hydro_result = hydro.apply(
            world,
            locations,
            coarse_hm,
            nodes=nodes or [],
            edges=edges or [],
        )
        coarse_hydro = hydro_result.cell_index.by_cell

    sparse_meter_hydro, meter_z_overrides = apply_declared_meter_river_carves(
        world,
        locations,
        coarse_hm.surface_z,
    )
    local_field = build_local_field_from_coarse(world, locations, pole_field, coarse_hm)

    return SurfaceTerrainContext(
        pole_field=pole_field,
        local_field=local_field,
        coarse_hm=coarse_hm,
        coarse_hydro=coarse_hydro,
        sparse_meter_hydro=sparse_meter_hydro,
        meter_z_overrides=meter_z_overrides,
        coarse_surface_z=dict(coarse_hm.surface_z),
    )
