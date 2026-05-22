from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.json_resolver import JsonResolver

router = APIRouter()


@router.get("/worlds/{world_id}/locations")
async def list_locations(world_id: str, container=Depends(get_container)) -> list[dict]:
    locs = await container.location_service().get_all(world_id)
    return [asdict(l) for l in locs]


@router.get("/worlds/{world_id}/locations/{location_uid}")
async def get_location(
    world_id: str,
    location_uid: str,
    container=Depends(get_container),
) -> dict:
    loc = await container.location_service().get_by_id(world_id, location_uid)
    return asdict(loc)


@router.get("/worlds/{world_id}/locations/{location_uid}/children")
async def get_children(
    world_id: str,
    location_uid: str,
    container=Depends(get_container),
) -> list[dict]:
    locs = await container.location_service().get_children(world_id, location_uid)
    return [asdict(l) for l in locs]


@router.post("/worlds/{world_id}/locations", status_code=201)
async def create_location(
    world_id: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    loc = await container.location_service().create(world_id, data)
    return asdict(loc)


@router.put("/worlds/{world_id}/locations/{location_uid}")
async def update_location(
    world_id: str,
    location_uid: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    loc = await container.location_service().update(world_id, location_uid, data)
    return asdict(loc)


@router.delete("/worlds/{world_id}/locations/{location_uid}", status_code=204)
async def delete_location(
    world_id: str,
    location_uid: str,
    container=Depends(get_container),
) -> None:
    await container.location_service().delete(world_id, location_uid)


@router.post("/worlds/{world_id}/locations/import")
async def import_locations(
    world_id: str,
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, list):
        raise HTTPException(status_code=422, detail="Locations JSON must be an array")
    result = await container.location_service().import_from_json(world_id, data)
    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())
