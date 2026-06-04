from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.json_resolver import JsonResolver
from app.api.utils.response_helpers import json_or_download
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService

router = APIRouter()

_terrain_generator = TerrainGeneratorService()


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

    world              = await world_svc.get_by_id(world_uid)
    locations          = await location_svc.get_all(world_uid)
    skip_location_uids = await map_svc.get_location_uids_with_cells(world_uid)

    cells  = _terrain_generator.generate_surface(world, locations,
                                                  skip_location_uids=skip_location_uids)
    result = await map_svc.save_generated(cells)

    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())
