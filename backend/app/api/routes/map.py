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
from app.application.worldData.generators.assemblers.climateAssembler import ClimateOrchestratorService
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
from app.application.worldData.generators.terrain.oresGenerator import generate_ores
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService

router = APIRouter()

_terrain_generator = TerrainGeneratorService()
_climate_orchestrator = ClimateOrchestratorService()
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


@router.post("/worlds/{world_uid}/map/generate-surface")
async def generate_surface(
    world_uid: str,
    container=Depends(get_container),
) -> JSONResponse:
    """Debug only — production: engine DAG node (same generators)."""
    map_svc      = container.map_cell_service()
    world_svc    = container.world_service()
    location_svc = container.location_service()

    world     = await world_svc.get_by_id(world_uid)
    locations = await location_svc.get_all(world_uid)

    result = await map_svc.save_terrain_batch(
        world_uid, _terrain_generator, world, locations,
    )

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())


@router.post("/worlds/{world_uid}/map/generate-hydrology")
async def generate_hydrology(
    world_uid: str,
    scope: str = Query(default="full"),
    container=Depends(get_container),
) -> JSONResponse:
    """
    Debug only — hydrology pass between surface and climate (D HY-7a target).

    Preview / stub until heightmap carve + persist wired in MapCellService.
    """
    map_svc       = container.map_cell_service()
    world_svc     = container.world_service()
    location_svc  = container.location_service()
    conn_svc      = container.connection_graph_service()

    world     = await world_svc.get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    cells = await map_svc.get_all(world_uid)
    if not cells:
        raise HTTPException(
            status_code=422,
            detail="No map cells — run generate-surface first",
        )

    locations = await location_svc.get_all(world_uid)
    nodes     = await conn_svc.get_nodes(world_uid)
    edges     = await conn_svc.get_edges(world_uid)

    scope_set = resolve_scopes(_parse_hydrology_scope(scope))
    pole_field = run_pole_resolve_pass(world, locations)
    heightmap, _n_eff = _terrain_generator.build_surface_heightmap(
        world, locations, pole_field,
    )
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

    return JSONResponse(content={
        "scope": scope,
        "scopes_active": sorted(s.value for s in scope_set),
        "stub": True,
        "cells_modified": 0,
        "river_segments": len(result.river_segments),
        "cell_roles": len(result.cell_index.roles),
    })


@router.post("/worlds/{world_uid}/map/generate-climate")
async def generate_climate(
    world_uid: str,
    container=Depends(get_container),
) -> JSONResponse:
    map_svc      = container.map_cell_service()
    world_svc    = container.world_service()
    location_svc = container.location_service()

    world     = await world_svc.get_by_id(world_uid)
    locations = await location_svc.get_all(world_uid)
    cells     = await map_svc.get_all(world_uid)
    if not cells:
        raise HTTPException(
            status_code=422,
            detail="No map cells — run generate-surface first",
        )

    climate_cells = _climate_orchestrator.apply_climate_pass(world, locations, cells)
    result        = await map_svc.save_pass(climate_cells, "climate")

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())


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
    map_svc      = container.map_cell_service()
    world_svc    = container.world_service()
    location_svc = container.location_service()

    world     = await world_svc.get_by_id(world_uid)
    locations = await location_svc.get_all(world_uid)

    result = await map_svc.save_z_slice(
        _terrain_generator, world, locations, gx, gy, z_lo, z_hi,
    )

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())
