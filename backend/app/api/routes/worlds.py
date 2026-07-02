from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.api.utils.responseHelpers import json_or_download

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
) -> JSONResponse:
    result = await container.world_service().update(world_uid, data)

    if result.requires_force:
        return JSONResponse(status_code=200, content={
            "warning": result.warning,
            "requires_force": True,
        })

    if result.map_cells_invalidated:
        await container.map_cell_service().clear(world_uid)

    return JSONResponse(status_code=200, content=asdict(result.world))


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
    results, rolled_back = await container.world_bundle_service().import_bundle(data)
    content = {k: v.to_dict() for k, v in results.items()}
    if rolled_back:
        failed_sections = [k for k, v in results.items() if v.failed > 0]
        content["rolled_back"] = True
        content["rollback_reason"] = f"failures in: {', '.join(failed_sections)}"
        status_code = 207
    else:
        status_code = 200
    return JSONResponse(status_code=status_code, content=content)
