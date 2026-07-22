"""Map debug HTTP — World Pack bake / refine / read / render.

Production materialization runs through **engine DAG nodes** (not these routes).

Canonical debug harness:
- ``POST …/map/pack/bake?mode=light|full|detailed`` — L0 / detailed L2 (WP-27)
  (detailed: ``scope=location|wilderness``; location needs ``location_uid``)
- ``POST …/map/refine-from-entry`` / ``schedule-chunk-refine``
- ``GET …/map/render-*``, ``pack/fine-terrain-read``, ``loading-progress``, ``bootstrap-tiles``

Legacy map_cells write routes (generate-surface / materialize-stack / …) are removed.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from dataclasses import asdict

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.api.utils.responseHelpers import json_or_download
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    require_surface_terrain_context,
)
from app.application.worldData.pack.refine.entryAnchorTracker import ANCHOR_KINDS, parse_anchor_kind
from app.application.worldData.materializationContext import resolve_materialization_context
from app.application.worldData.pack.bake.packBakeFinalize import finalize_pack_on_world
from app.application.worldData.pack.read.parentLightLoad import MissingParentLightError
from app.core.generationLogging import generation_world_log
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.dataModel.worldPack.detailedBakeScope import DetailedBakeScopeKind
from app.dataModel.worldPack.packBakeMode import PackBakeApiMode
from app.dataModel.worldPack.packTilePlan import PackTilePlanScope

router = APIRouter()
_hydrology_generator = HydrologyGeneratorService()


@router.get("/worlds/{world_uid}/map/loading-progress")
async def get_loading_progress(
    world_uid: str,
    container=Depends(get_container),
) -> dict:
    facade = container.map_cell_read_service(world_uid)
    world_svc = container.world_service()
    location_svc = container.location_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
    locations = await location_svc.get_all(world_uid)
    return facade.pack.loading.get_loading_progress(world, locations=locations).to_dict()


@router.get("/worlds/{world_uid}/map/bootstrap-tiles")
async def list_bootstrap_tiles(
    world_uid: str,
    max_tiles: int = Query(
        default=0,
        ge=0,
        description="Debug cap for light scope; 0=uncapped (product default)",
    ),
    scope: PackTilePlanScope = Query(default="light"),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — macro tiles selected for L0 bake (no persist)."""
    stack = container.surface_materialization_orchestrator()
    world_svc = container.world_service()
    location_svc = container.location_service()
    conn_svc = container.connection_graph_service()

    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    locations = await location_svc.get_all(world_uid)
    nodes = await conn_svc.get_nodes(world_uid)
    edges = await conn_svc.get_edges(world_uid)
    try:
        plan = stack.plan_bootstrap_tiles(
            world, locations,
            scope=scope,
            max_tiles=max_tiles,
            nodes=nodes, edges=edges,
            hydrology_generator=_hydrology_generator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JSONResponse(content={
        "world_uid": world_uid,
        "scope": plan.scope,
        "max_tiles": plan.cap_applied,
        "capped": plan.capped,
        "tile_count": len(plan.tiles),
        "tiles": [{"gx": t.gx, "gy": t.gy} for t in plan.tiles],
    })


@router.post("/worlds/{world_uid}/map/pack/bake")
async def bake_world_pack(
    world_uid: str,
    mode: PackBakeApiMode = Query(default="light"),
    max_tiles: int = Query(
        default=0,
        ge=0,
        description=(
            "Debug cap: light_bake location tiles; detailed scope=wilderness L0 tiles; "
            "0=uncapped"
        ),
    ),
    scope: DetailedBakeScopeKind | None = Query(
        default=None,
        description="detailed only: location | wilderness (required unless location_uid)",
    ),
    location_uid: str | None = Query(
        default=None,
        description="detailed scope=location: required location_uid",
    ),
    tile_gx: int | None = Query(
        default=None,
        description="detailed scope=wilderness: single macro-tile gx (with tile_gy)",
    ),
    tile_gy: int | None = Query(
        default=None,
        description="detailed scope=wilderness: single macro-tile gy (with tile_gx)",
    ),
    anchor_x: int | None = Query(default=None),
    anchor_y: int | None = Query(default=None),
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — bake World Pack: light_bake / full_bake / detailed_bake (WP-27).

    L0 only for light/full. L2 offline: ``mode=detailed&scope=location|wilderness``.
    Wilderness debug unit: ``tile_gx``+``tile_gy`` (one macro-cell per request).
    Entry/runtime L2 → ``POST …/map/refine-from-entry``.
    """
    stack = container.surface_materialization_orchestrator()
    world_svc = container.world_service()
    location_svc = container.location_service()
    conn_svc = container.connection_graph_service()

    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
    locations = await location_svc.get_all(world_uid)
    nodes = await conn_svc.get_nodes(world_uid)
    edges = await conn_svc.get_edges(world_uid)
    mat_ctx = resolve_materialization_context(
        world, free_cores=free_cores, parallel_workers_override=parallel_workers,
    )
    writer = container.world_pack_writer_for(world)

    try:
        result = await stack.bake_pack(
            world_uid, world, locations, mat_ctx, writer,
            mode=mode,
            max_tiles=max_tiles,
            location_uid=location_uid,
            detailed_scope=scope,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            nodes=nodes, edges=edges, hydrology_generator=_hydrology_generator,
            anchor_x=anchor_x, anchor_y=anchor_y,
        )
    except MissingParentLightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    progress = container.map_cell_read_service(world_uid).pack.loading.get_loading_progress(
        world, locations=locations,
    )
    result.loading_progress = progress.to_dict()
    status_code = 200 if result.terrain_failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())


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
    """Debug only — ASCII world map (pack: L0 light tiles; legacy: map_cells)."""
    from app.application.worldData.render.mapGridRenderService import MapGridRenderService

    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    svc = MapGridRenderService(container.map_cell_service())
    bbox = (gx0, gy0, gx1, gy1)
    if any(v is not None for v in bbox) and not all(v is not None for v in bbox):
        raise HTTPException(
            status_code=422,
            detail="Provide all bbox query params (gx0, gy0, gx1, gy1) or omit all",
        )
    payload = await svc.render_world_grid(
        world,
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
    """Debug only — per macro tile (pack: L0 light grid; legacy: fine meters)."""
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
    """Debug only — ASCII per location with location_terrain (pack) or map_cells (legacy)."""
    from app.application.worldData.render.mapGridRenderService import MapGridRenderService

    world_svc = container.world_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    svc = MapGridRenderService(container.map_cell_service())
    payload = await svc.render_all_location_grids(world)
    return JSONResponse(content=payload)



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
    z_above: int = Query(default=SceneVolumePolicy.canonical_defaults().scene_z_above, ge=0),
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


@router.post("/worlds/{world_uid}/map/refine-from-entry")
async def refine_from_entry_route(
    world_uid: str,
    x: int,
    y: int,
    kind: str = Query(
        default="session_start",
        pattern="^(" + "|".join(ANCHOR_KINDS) + ")$",
    ),
    location_uid: str | None = Query(default=None),
    heading_dx: int | None = Query(default=None),
    heading_dy: int | None = Query(default=None),
    schedule_bg: bool = Query(
        default=True,
        description="If true, also call schedule_chunk_refine after blocking refine",
    ),
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — WP-13 blocking entry refine; optional schedule_chunk_refine (no DAG)."""
    world_svc = container.world_service()
    location_svc = container.location_service()
    conn_svc = container.connection_graph_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
    locations = await location_svc.get_all(world_uid)
    nodes = await conn_svc.get_nodes(world_uid)
    edges = await conn_svc.get_edges(world_uid)
    try:
        surface_ctx = require_surface_terrain_context(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=_hydrology_generator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    mat_ctx = resolve_materialization_context(
        world, free_cores=free_cores, parallel_workers_override=parallel_workers,
    )
    writer = container.world_pack_writer_for(world)
    entry_orch = container.entry_refine_orchestrator()
    try:
        anchor_kind = parse_anchor_kind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        with generation_world_log(world_uid, mode="entry"):
            entry = await entry_orch.refine_from_entry(
                world_uid, world, locations, writer, mat_ctx, surface_ctx,
                kind=anchor_kind,
                anchor_x=x,
                anchor_y=y,
                location_uid=location_uid,
                heading_dx=heading_dx,
                heading_dy=heading_dy,
            )
            scheduled = None
            if schedule_bg:
                scheduled = await entry_orch.schedule_chunk_refine(
                    world_uid, world, locations, writer, mat_ctx, surface_ctx,
                    anchor_x=x,
                    anchor_y=y,
                    tile_gx=entry.tile_gx,
                    tile_gy=entry.tile_gy,
                    heading=entry.heading,
                )
            await finalize_pack_on_world(
                world_svc,
                world,
                writer,
                read_context=container.pack_read_services(world_uid).context,
            )
    except MissingParentLightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(content={
        "world_uid": world_uid,
        "kind": entry.anchor.kind,
        "anchor": {
            "x": entry.anchor.entry_x,
            "y": entry.anchor.entry_y,
            "tile_gx": entry.tile_gx,
            "tile_gy": entry.tile_gy,
            "location_uid": entry.anchor.location_uid,
        },
        "terrain": entry.terrain.to_dict(),
        "chunks_done": entry.chunks_done,
        "chunks_total": entry.chunks_total,
        "climate_fine_tiles": scheduled.climate_fine_tiles if scheduled else 0,
        "refine_queue_depth": (
            scheduled.queue_depth if scheduled else len(entry_orch.refine_queue)
        ),
        "scheduled_enqueued": scheduled.enqueued if scheduled else 0,
        "schedule_bg": schedule_bg,
        "background_expand_radius_m": (
            SceneVolumePolicy.canonical_defaults().background_expand_radius_m
        ),
    })


@router.post("/worlds/{world_uid}/map/schedule-chunk-refine")
async def schedule_chunk_refine_route(
    world_uid: str,
    x: int,
    y: int,
    tile_gx: int | None = Query(default=None),
    tile_gy: int | None = Query(default=None),
    heading_dx: int | None = Query(default=None),
    heading_dy: int | None = Query(default=None),
    free_cores: int | None = Query(default=None, ge=1),
    parallel_workers: int | None = Query(default=None, ge=1),
    container=Depends(get_container),
) -> JSONResponse:
    """Debug — WP-13 background rings + path-ahead only (no blocking scene)."""
    world_svc = container.world_service()
    location_svc = container.location_service()
    conn_svc = container.connection_graph_service()
    world = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")
    locations = await location_svc.get_all(world_uid)
    nodes = await conn_svc.get_nodes(world_uid)
    edges = await conn_svc.get_edges(world_uid)
    try:
        surface_ctx = require_surface_terrain_context(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=_hydrology_generator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    mat_ctx = resolve_materialization_context(
        world, free_cores=free_cores, parallel_workers_override=parallel_workers,
    )
    writer = container.world_pack_writer_for(world)
    entry_orch = container.entry_refine_orchestrator()
    try:
        scheduled = await entry_orch.schedule_chunk_refine(
            world_uid, world, locations, writer, mat_ctx, surface_ctx,
            anchor_x=x,
            anchor_y=y,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            heading_dx=heading_dx,
            heading_dy=heading_dy,
        )
        await finalize_pack_on_world(
            world_svc,
            world,
            writer,
            read_context=container.pack_read_services(world_uid).context,
        )
    except MissingParentLightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(content={
        "world_uid": world_uid,
        "anchor": {"x": x, "y": y, "tile_gx": tile_gx, "tile_gy": tile_gy},
        "enqueued": scheduled.enqueued,
        "refine_queue_depth": scheduled.queue_depth,
        "climate_fine_tiles": scheduled.climate_fine_tiles,
        "background_expand_radius_m": (
            SceneVolumePolicy.canonical_defaults().background_expand_radius_m
        ),
    })
