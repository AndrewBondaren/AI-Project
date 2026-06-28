from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.json_resolver import JsonResolver
from app.api.utils.response_helpers import json_or_download
from app.application.worldData.generators.assemblers.climateAssembler import ClimateOrchestratorService
from app.application.worldData.generators.terrain.cavesGenerator import generate_caves
from app.application.worldData.generators.terrain.oresGenerator import generate_ores
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService

router = APIRouter()

_terrain_generator = TerrainGeneratorService()
_climate_orchestrator = ClimateOrchestratorService()


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

    cells  = _terrain_generator.generate_z_slice(world, locations, gx, gy, z_lo, z_hi)
    result = await map_svc.save_pass(cells, "terrain")

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())
