from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.json_resolver import JsonResolver

router = APIRouter()


@router.get("/worlds")
async def list_worlds(container=Depends(get_container)) -> list[dict]:
    worlds = await container.world_service().get_all()
    return [asdict(w) for w in worlds]


@router.get("/worlds/{world_uid}")
async def get_world(world_uid: str, container=Depends(get_container)) -> dict:
    world = await container.world_service().get_by_id(world_uid)
    return asdict(world)


@router.post("/worlds", status_code=201)
async def create_world(data: dict[str, Any], container=Depends(get_container)) -> dict:
    world = await container.world_service().create(data)
    return asdict(world)


@router.put("/worlds/{world_uid}")
async def update_world(
    world_uid: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    world = await container.world_service().update(world_uid, data)
    return asdict(world)


@router.delete("/worlds/{world_uid}", status_code=204)
async def delete_world(world_uid: str, container=Depends(get_container)) -> None:
    await container.world_service().delete(world_uid)


@router.post("/worlds/import")
async def import_world(
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> dict:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="World JSON must be an object, not an array")
    result = await container.world_service().import_from_json(data)
    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())
