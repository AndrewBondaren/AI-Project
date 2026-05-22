from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.json_resolver import JsonResolver
from app.api.utils.response_helpers import json_or_download

router = APIRouter()


@router.get("/worlds")
async def list_worlds(container=Depends(get_container)) -> list[dict]:
    worlds = await container.world_service().get_all()
    return [asdict(w) for w in worlds]


@router.get("/worlds/{world_uid}/export")
async def export_world(
    world_uid: str,
    download: bool = False,
    container=Depends(get_container),
) -> JSONResponse:
    bundle = await container.world_bundle_service().export(world_uid)
    return json_or_download(bundle, download, f"world_{world_uid}.json")


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
) -> JSONResponse:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="World bundle JSON must be an object")
    results = await container.world_bundle_service().import_bundle(data)
    has_failures = any(r.failed > 0 for r in results.values())
    status_code = 207 if has_failures else 200
    return JSONResponse(status_code=status_code, content={k: v.to_dict() for k, v in results.items()})
