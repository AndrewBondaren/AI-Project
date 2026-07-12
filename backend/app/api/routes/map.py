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
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.types import (
    HydrologyScope,
    resolve_scopes,
)
from app.application.worldData.generators.terrain.passes.columnFillPass import run_column_fill
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass
from app.application.worldData.generators.terrain.oresGenerator import generate_ores
from dataclasses import asdict

from app.application.worldData.materializationContext import resolve_materialization_context
from app.application.worldData.parallelPolicy import resolve_terrain_workers
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults

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


@router.get("/worlds/{world_uid}/map/loading-progress")
async def get_loading_progress(
    world_uid: str,
    container=Depends(get_container),
) -> dict:
    facade = container.map_cell_read_service(world_uid)
    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
    return facade.pack.loading.get_loading_progress(world).to_dict()


@router.get("/worlds/{world_uid}/map/pack/fine-terrain-read")
async def pack_fine_terrain_read(
    world_uid: str,
    gx: int | None = Query(default=None),
    gy: int | None = Query(default=None),
    cx: int | None = Query(default=None),
    cy: int | None = Query(default=None),
    location_uid: str | None = Query(default=None),
    x: int | None = Query(default=None),
    y: int | None = Query(default=None),
    z: int | None = Query(default=None),
    sample_columns: int = Query(default=3, ge=0, le=32),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — inspect fine terrain read from pack (manifest + blob + merge).

    Modes (mutually exclusive):
    - ``location_uid`` — location terrain ``locations/l.{uid}.terrain.zst``
    - ``gx,gy,cx,cy`` — wilderness chunk ``tiles/r.{gx}.{gy}.c.{cx}.{cy}.zst``
    - ``gx,gy`` — tile manifest entry + chunk index
    - ``x,y,z`` — gameplay merge at world meter cell (layer priority WP-20)
    """
    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    read = container.map_cell_read_service(world_uid)
    fine = read.pack.fine_terrain_read

    if location_uid:
        payload = fine.read_location_terrain(world, location_uid, sample_columns=sample_columns)
    elif gx is not None and gy is not None and cx is not None and cy is not None:
        payload = fine.read_wilderness_chunk(
            world, gx, gy, cx, cy, sample_columns=sample_columns,
        )
    elif gx is not None and gy is not None:
        payload = fine.read_tile(world, gx, gy)
    elif x is not None and y is not None and z is not None:
        payload = await fine.read_merged_cell(world, x, y, z)
    else:
        raise HTTPException(
            status_code=422,
            detail=(
                "Specify one read mode: location_uid; or gx,gy,cx,cy; or gx,gy; or x,y,z"
            ),
        )

    if not payload.get("ok", True):
        raise HTTPException(status_code=404, detail=payload.get("error", "read failed"))
    return JSONResponse(content=payload)


@router.get("/worlds/{world_uid}/map")
async def list_map_cells(
    world_uid: str,
    container=Depends(get_container),
) -> list[dict]:
    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
    cells = await container.map_cell_service().get_all_for_read(world)
    return [asdict(c) for c in cells]


@router.get("/worlds/{world_uid}/map/export")
async def export_map(
    world_uid: str,
    download: bool = False,
    container=Depends(get_container),
) -> JSONResponse:
    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
    data = await container.map_cell_service().export_for_debug(world)
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

    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    location_svc = container.location_service()
    locations = await location_svc.get_all(world_uid)
    svc = MapGridRenderService(container.map_cell_service())
    bbox = (gx0, gy0, gx1, gy1)
    if any(v is not None for v in bbox) and not all(v is not None for v in bbox):
        raise HTTPException(
            status_code=422,
            detail="Provide all bbox query params (gx0, gy0, gx1, gy1) or omit all",
        )
    payload = await svc.render_world_grid(
        world,
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

    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    svc = MapGridRenderService(container.map_cell_service())
    payload = await svc.render_world_tile_grids(world)
    return JSONResponse(content=payload)


@router.get("/worlds/{world_uid}/map/render-location-grids")
async def render_all_location_grids(
    world_uid: str,
    container=Depends(get_container),
) -> JSONResponse:
    """Debug only — ASCII per location_uid that has map_cells, all z levels."""
    from app.application.worldData.render.mapGridRenderService import MapGridRenderService

    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    svc = MapGridRenderService(container.map_cell_service())
    payload = await svc.render_all_location_grids(world)
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
    max_tiles: int = Query(default=PackBakeDefaults.canonical_defaults().max_tiles_light, ge=0),
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
    max_tiles: int = Query(default=PackBakeDefaults.canonical_defaults().max_tiles_light, ge=0),
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
    try:
        map_svc.reject_legacy_generate_on_pack(world)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    try:
        map_svc.reject_legacy_generate_on_pack(world)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{exc} Use POST /worlds/{{uid}}/map/pack/bake for coarse climate_coarse.",
        ) from exc

    locations = await location_svc.get_all(world_uid)
    cells     = await map_svc.get_all_for_read(world)
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


@router.post("/worlds/{world_uid}/map/pack/bake")
async def bake_world_pack(
    world_uid: str,
    mode: str = Query(default="light", pattern="^(light|tile|full)$"),
    max_tiles: int = Query(default=PackBakeDefaults.canonical_defaults().max_tiles_light, ge=0),
    anchor_x: int | None = Query(default=None),
    anchor_y: int | None = Query(default=None),
    heading_dx: int | None = Query(default=None),
    heading_dy: int | None = Query(default=None),
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — bake World Pack (world_map light + optional scene fine-terrain chunks)."""
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
    writer = container.world_pack_writer_for(world)

    if mode == "light":
        report = await stack.materialize_pack_light(
            world_uid, world, locations, mat_ctx, writer,
            max_tiles=cap,
            nodes=nodes, edges=edges, hydrology_generator=_hydrology_generator,
            anchor_x=anchor_x, anchor_y=anchor_y,
            heading_dx=heading_dx, heading_dy=heading_dy,
            pack_orchestrator=container.pack_materialization_orchestrator(),
        )
    else:
        raise HTTPException(status_code=422, detail=f"pack bake mode '{mode}' not implemented yet")

    progress = container.map_cell_read_service(world_uid).pack.loading.get_loading_progress(world)
    status_code = 200 if report.terrain.failed == 0 else 207
    return JSONResponse(status_code=status_code, content={
        **report.to_dict(),
        "pack_mode": mode,
        "loading_progress": progress.to_dict(),
    })


@router.post("/worlds/{world_uid}/map/materialize-stack")
async def materialize_stack(
    world_uid: str,
    mode: str = Query(default="bootstrap", pattern="^(bootstrap|full)$"),
    target: str = Query(default="legacy", pattern="^(legacy|pack)$"),
    max_tiles: int = Query(default=PackBakeDefaults.canonical_defaults().max_tiles_light, ge=0),
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    chunks_per_commit: int | None = Query(default=None, ge=1),
    insert_only: bool | None = Query(default=None),
    bulk_pragmas: bool = Query(default=True),
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
        chunks_per_commit=chunks_per_commit,
        insert_only=insert_only,
        bulk_write_pragmas=bulk_pragmas,
    )

    if target == "pack":
        writer = container.world_pack_writer_for(world)
        report = await stack.materialize_pack_light(
            world_uid, world, locations, mat_ctx, writer,
            max_tiles=cap,
            nodes=nodes, edges=edges, hydrology_generator=_hydrology_generator,
            pack_orchestrator=container.pack_materialization_orchestrator(),
        )
        progress = container.map_cell_read_service(world_uid).pack.loading.get_loading_progress(world)
        status_code = 200 if report.terrain.failed == 0 else 207
        return JSONResponse(
            status_code=status_code,
            headers={"Deprecation": "true", "Link": '</worlds/{}/map/pack/bake>; rel="successor-version"'.format(world_uid)},
            content={
                **report.to_dict(),
                "target": "pack",
                "loading_progress": progress.to_dict(),
                "deprecated": "Use POST /worlds/{uid}/map/pack/bake instead",
            },
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
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    cells = await map_svc.get_all_for_read(world)
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
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    cells = await map_svc.get_all_for_read(world)
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


@router.get("/worlds/{world_uid}/map/has-column")
async def has_column_cells_route(
    world_uid: str,
    x: int,
    y: int,
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — TR-LAZY-LOAD: any cells at fine column (x, y)?"""
    map_svc = container.map_cell_service()
    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
    found = await map_svc.has_column_cells(world_uid, x, y, world=world)
    return JSONResponse(content={"world_uid": world_uid, "x": x, "y": y, "has_column": found})


@router.get("/worlds/{world_uid}/map/scene-volume")
async def scene_volume_route(
    world_uid: str,
    x: int,
    y: int,
    z: int,
    xy_radius: int = Query(default=SceneVolumePolicy.canonical_defaults().scene_xy_radius, ge=0),
    z_below: int | None = Query(default=None, ge=0),
    z_above: int = Query(default=0, ge=0),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — TR-LAZY-LOAD: 3D bbox around scene anchor (no DAG)."""
    map_svc = container.map_cell_service()
    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    cells = await map_svc.get_scene_volume(
        world, x, y, z, xy_radius=xy_radius, z_below=z_below, z_above=z_above,
    )
    return JSONResponse(content={
        "world_uid": world_uid,
        "anchor": {"x": x, "y": y, "z": z},
        "xy_radius": xy_radius,
        "cell_count": len(cells),
        "cells": [asdict(c) for c in cells],
    })
