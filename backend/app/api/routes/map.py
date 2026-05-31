from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.json_resolver import JsonResolver
from app.api.utils.response_helpers import json_or_download

router = APIRouter()


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
