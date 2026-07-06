"""Map cell CRUD and generation pass hooks.

Production materialization (world load, gameplay) must run through **engine DAG nodes**
— same generator functions, no HTTP.

``POST …/map/generate-*`` routes are a **permanent debug harness** for point testing
(``debug_settlement.py``, manual curl, isolated pass runs). Keep them; do not wire
frontend or player flows to these endpoints.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.api.utils.responseHelpers import json_or_download
from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.terrain.cavesGenerator import generate_caves
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.hydrology.types import (
    HydrologyScope,
    resolve_scopes,
)
from app.application.worldData.generators.terrain.passes.columnFillPass import run_column_fill
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass
from app.application.worldData.generators.terrain.oresGenerator import generate_ores
from app.application.worldData.materializationContext import resolve_materialization_context
from app.application.worldData.parallelPolicy import resolve_terrain_workers

router = APIRouter()
_hydrology_generator = HydrologyGeneratorService()

_HYDROLOGY_SCOPE_QUERY: dict[str, frozenset[HydrologyScope]] = {
    "ocean":     frozenset({HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN}),
    "lakes":     frozenset({HydrologyScope.LAKES}),
    "rivers":    frozenset({HydrologyScope.RIVERS}),
    "landforms": frozenset({HydrologyScope.LANDFORMS}),
}


def _parse_hydrology_scope(scope: str) -> frozenset[HydrologyScope] | None:
    key = scope.lower().strip()
    if key == "full":
        return None
    parsed = _HYDROLOGY_SCOPE_QUERY.get(key)
    if parsed is None:
        allowed = ", ".join(["full", *_HYDROLOGY_SCOPE_QUERY])
        raise HTTPException(status_code=422, detail=f"Unknown hydrology scope '{scope}'. Use: {allowed}")
    return parsed


@router.get("/worlds/{world_uid}/map")
async def list_map_cells(
    world_uid: str,
    container=Depends(get_container),
) -> list[dict]:
    return await container.map_cell_service().export(world_uid)


@router.get("/worlds/{world_uid}/map/export")
async def export_map(
    world_uid: str,
    download: bool = False,
    container=Depends(get_container),
) -> JSONResponse:
    data = await container.map_cell_service().export(world_uid)
    return json_or_download(data, download, f"map_{world_uid}.json")


@router.post("/worlds/{world_uid}/map/import")
async def import_map(
    
    world_uid: str,
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, list):
        raise HTTPException(status_code=422, detail="Map cells JSON must be an array")
    result = await container.map_cell_service().import_from_json(world_uid, data)
    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())


@router.delete("/worlds/{world_uid}/map", status_code=204)
async def clear_map(
    world_uid: str,
    container=Depends(get_container),
) -> None:
    await container.map_cell_service().clear(world_uid)


@router.get("/worlds/{world_uid}/map/render-world-grid")
async def render_world_grid(
    world_uid: str,
    gx0: int | None = Query(default=None),
    gy0: int | None = Query(default=None),
    gx1: int | None = Query(default=None),
    gy1: int | None = Query(default=None),
    mark_locations: bool = Query(default=True),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug only — ASCII top-surface world map (@ = cell has location_uid)."""
    from app.application.worldData.render.mapGridRenderService import MapGridRenderService

    location_svc = container.location_service()
    locations = await location_svc.get_all(world_uid)
    svc = MapGridRenderService(
        container.map_cell_service(),
        world_service=container.world_service(),
    )
    bbox = (gx0, gy0, gx1, gy1)
    if any(v is not None for v in bbox) and not all(v is not None for v in bbox):
        raise HTTPException(
            status_code=422,
            detail="Provide all bbox query params (gx0, gy0, gx1, gy1) or omit all",
        )
    payload = await svc.render_world_grid(
        world_uid,
        locations=locations,
        gx0=gx0,
        gy0=gy0,
        gx1=gx1,
        gy1=gy1,
        mark_locations=mark_locations,
    )
    return JSONResponse(content=payload)


@router.get("/worlds/{world_uid}/map/render-world-tile-grids")
async def render_world_tile_grids(
    world_uid: str,
    container=Depends(get_container),
) -> JSONResponse:
    """Debug only — per macro tile fine grid (map_cell_size_m² cells)."""
    from app.application.worldData.render.mapGridRenderService import MapGridRenderService

    svc = MapGridRenderService(
        container.map_cell_service(),
        world_service=container.world_service(),
    )
    payload = await svc.render_world_tile_grids(world_uid)
    return JSONResponse(content=payload)


@router.get("/worlds/{world_uid}/map/render-location-grids")
async def render_all_location_grids(
    world_uid: str,
    container=Depends(get_container),
) -> JSONResponse:
    """Debug only — ASCII per location_uid that has map_cells, all z levels."""
    from app.application.worldData.render.mapGridRenderService import MapGridRenderService

    svc = MapGridRenderService(
        container.map_cell_service(),
        world_service=container.world_service(),
    )
    payload = await svc.render_all_location_grids(world_uid)
    return JSONResponse(content=payload)


@router.post("/worlds/{world_uid}/map/materialize-tile")
async def materialize_tile(
    world_uid: str,
    gx: int = Query(...),
    gy: int = Query(...),
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — fine grid for one macro tile (map_cell_size_m² surface cells + subsurface)."""
    terrain_orch = container.terrain_batch_orchestrator()
    world_svc = container.world_service()
    location_svc = container.location_service()
    conn_svc = container.connection_graph_service()

    world = await world_svc.get_by_id(world_uid)
    locations = await location_svc.get_all(world_uid)
    nodes = await conn_svc.get_nodes(world_uid)
    edges = await conn_svc.get_edges(world_uid)
    mat_ctx = resolve_materialization_context(
        world, free_cores=free_cores, parallel_workers_override=parallel_workers,
    )

    result, chunks_done, chunks_total = await terrain_orch.materialize_macro_tile(
        world_uid, world, locations, gx, gy, mat_ctx,
        nodes=nodes, edges=edges, hydrology_generator=_hydrology_generator,
    )
    status_code = 200 if result.failed == 0 else 207
    payload = {
        **result.to_dict(),
        "chunks_done": chunks_done,
        "chunks_total": chunks_total,
        "terrain_workers": resolve_terrain_workers(mat_ctx, world),
    }
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/worlds/{world_uid}/map/bootstrap-tiles")
async def list_bootstrap_tiles(
    world_uid: str,
    max_tiles: int = Query(default=16, ge=0),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — macro tiles selected for bootstrap surface init (no persist)."""
    terrain_orch = container.terrain_batch_orchestrator()
    world_svc = container.world_service()
    location_svc = container.location_service()
    conn_svc = container.connection_graph_service()

    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    locations = await location_svc.get_all(world_uid)
    nodes = await conn_svc.get_nodes(world_uid)
    edges = await conn_svc.get_edges(world_uid)

    cap = max_tiles if max_tiles > 0 else None
    tiles = terrain_orch.plan_bootstrap_tiles(
        world, locations, nodes=nodes, edges=edges,
        hydrology_generator=_hydrology_generator, max_tiles=cap,
    )
    return JSONResponse(content={
        "world_uid": world_uid,
        "max_tiles": cap,
        "tile_count": len(tiles),
        "tiles": [{"gx": gx, "gy": gy} for gx, gy in tiles],
    })


@router.post("/worlds/{world_uid}/map/generate-surface")
async def generate_surface(
    world_uid: str,
    mode: str = Query(default="bootstrap", pattern="^(bootstrap|full)$"),
    max_tiles: int = Query(default=16, ge=0),
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug only — production: engine DAG node (same generators).

    ``mode=bootstrap`` (default): full fine grid for priority macro tiles only.
    ``mode=full``: entire location bbox — can be billions of cells at map_cell_size_m=3000.
    """
    terrain_orch = container.terrain_batch_orchestrator()
    world_svc    = container.world_service()
    location_svc = container.location_service()
    conn_svc     = container.connection_graph_service()

    world     = await world_svc.get_by_id(world_uid)
    locations = await location_svc.get_all(world_uid)
    nodes     = await conn_svc.get_nodes(world_uid)
    edges     = await conn_svc.get_edges(world_uid)

    cap = max_tiles if max_tiles > 0 else None
    mat_ctx = resolve_materialization_context(
        world, free_cores=free_cores, parallel_workers_override=parallel_workers,
    )
    tiles_preview: list[tuple[int, int]] = []
    if mode == "bootstrap":
        tiles_preview = terrain_orch.plan_bootstrap_tiles(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=_hydrology_generator, max_tiles=cap,
        )

    result, chunks_done, chunks_total = await terrain_orch.save_terrain_batch(
        world_uid, world, locations, mat_ctx,
        nodes=nodes, edges=edges, hydrology_generator=_hydrology_generator,
        surface_mode=mode,  # type: ignore[arg-type]
        max_tiles=cap,
    )

    status_code = 200 if result.failed == 0 else 207
    payload = {
        **result.to_dict(),
        "mode": mode,
        "max_tiles": cap,
        "chunks_done": chunks_done,
        "chunks_total": chunks_total,
        "terrain_workers": resolve_terrain_workers(mat_ctx, world),
    }
    if mode == "bootstrap":
        payload["tile_count"] = len(tiles_preview)
        payload["tiles"] = [{"gx": gx, "gy": gy} for gx, gy in tiles_preview]
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/worlds/{world_uid}/map/generate-hydrology")
async def generate_hydrology(
    world_uid: str,
    scope: str = Query(default="full"),
    container=Depends(get_container),
) -> JSONResponse:
    """
    Debug only — hydrology pass between surface and climate (D HY-7a target).

    Preview / stub until heightmap carve + persist wired in terrain batch orchestrator.
    """
    map_svc       = container.map_cell_service()
    world_svc     = container.world_service()
    location_svc  = container.location_service()
    conn_svc      = container.connection_graph_service()

    world     = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    locations = await location_svc.get_all(world_uid)
    nodes     = await conn_svc.get_nodes(world_uid)
    edges     = await conn_svc.get_edges(world_uid)

    scope_set = resolve_scopes(_parse_hydrology_scope(scope))
    pole_field = run_pole_resolve_pass(world, locations)
    heightmap = run_surface_pass(world, locations, pole_field)
    if heightmap is None:
        raise HTTPException(
            status_code=422,
            detail="Empty heightmap — add static location anchors or bounds",
        )

    result = _hydrology_generator.apply(
        world,
        locations,
        heightmap,
        nodes=nodes,
        edges=edges,
        scopes=scope_set,
    )

    n_eff = run_gap_analysis(world, heightmap)
    cells = run_column_fill(
        world,
        heightmap,
        n_eff,
        hydrology_by_cell=result.cell_index.by_cell or None,
    )
    save_result = await map_svc.save_pass(cells, "terrain")

    status_code = 200 if save_result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content={
        "scope": scope,
        "scopes_active": sorted(s.value for s in scope_set),
        "cells_modified": result.cells_modified,
        "river_segments": len(result.river_segments),
        "cell_roles": len(result.cell_index.roles),
        "terrain_upserted": save_result.succeeded,
        "total": save_result.total,
    })


@router.post("/worlds/{world_uid}/map/generate-climate")
async def generate_climate(
    world_uid: str,
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    container=Depends(get_container),
) -> JSONResponse:
    map_svc      = container.map_cell_service()
    world_svc    = container.world_service()
    location_svc = container.location_service()
    climate_orch = container.climate_batch_orchestrator()

    world     = await world_svc.get_by_id(world_uid)
    locations = await location_svc.get_all(world_uid)
    cells     = await map_svc.get_all(world_uid)
    if not cells:
        raise HTTPException(
            status_code=422,
            detail="No map cells — run generate-surface first",
        )

    mat_ctx = resolve_materialization_context(
        world, free_cores=free_cores, parallel_workers_override=parallel_workers,
    )
    result, batches_done, batches_total = await climate_orch.apply_climate_batch(
        world_uid, world, locations, mat_ctx, cells=cells,
    )

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content={
        **result.to_dict(),
        "batches_done": batches_done,
        "batches_total": batches_total,
    })


@router.post("/worlds/{world_uid}/map/materialize-stack")
async def materialize_stack(
    world_uid: str,
    mode: str = Query(default="bootstrap", pattern="^(bootstrap|full)$"),
    max_tiles: int = Query(default=16, ge=0),
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    include_climate: bool = Query(default=True),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — S→CL surface stack (terrain + hydrology + climate)."""
    stack = container.surface_materialization_orchestrator()
    world_svc = container.world_service()
    location_svc = container.location_service()
    conn_svc = container.connection_graph_service()

    world = await world_svc.get_by_id(world_uid)
    locations = await location_svc.get_all(world_uid)
    nodes = await conn_svc.get_nodes(world_uid)
    edges = await conn_svc.get_edges(world_uid)
    cap = max_tiles if max_tiles > 0 else None
    mat_ctx = resolve_materialization_context(
        world, free_cores=free_cores, parallel_workers_override=parallel_workers,
    )

    report = await stack.materialize_surface_stack(
        world_uid, world, locations, mat_ctx,
        surface_mode=mode,  # type: ignore[arg-type]
        max_tiles=cap,
        include_climate=include_climate,
        nodes=nodes, edges=edges, hydrology_generator=_hydrology_generator,
    )
    status_code = 200 if report.terrain.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=report.to_dict())


@router.post("/worlds/{world_uid}/map/generate-ores")
async def generate_ores_route(
    world_uid: str,
    container=Depends(get_container),
) -> JSONResponse:
    map_svc   = container.map_cell_service()
    world_svc = container.world_service()

    world = await world_svc.get_by_id(world_uid)
    cells = await map_svc.get_all(world_uid)
    if not cells:
        raise HTTPException(status_code=422, detail="No map cells — run generate-surface first")

    ore_cells = generate_ores(world, cells)
    result    = await map_svc.save_pass(ore_cells, "ore")

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())


@router.post("/worlds/{world_uid}/map/generate-caves")
async def generate_caves_route(
    world_uid: str,
    container=Depends(get_container),
) -> JSONResponse:
    map_svc   = container.map_cell_service()
    world_svc = container.world_service()

    world = await world_svc.get_by_id(world_uid)
    cells = await map_svc.get_all(world_uid)
    if not cells:
        raise HTTPException(status_code=422, detail="No map cells — run generate-surface first")

    cave_cells = generate_caves(world, cells)
    result     = await map_svc.save_pass(cave_cells, "cave")

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())


@router.post("/worlds/{world_uid}/map/generate-z-slice")
async def generate_z_slice_route(
    world_uid: str,
    gx: int,
    gy: int,
    z_lo: int,
    z_hi: int,
    container=Depends(get_container),
) -> JSONResponse:
    terrain_orch = container.terrain_batch_orchestrator()
    world_svc    = container.world_service()
    location_svc = container.location_service()

    world     = await world_svc.get_by_id(world_uid)
    locations = await location_svc.get_all(world_uid)

    result = await terrain_orch.save_z_slice(
        world, locations, gx, gy, z_lo, z_hi,
    )

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())
