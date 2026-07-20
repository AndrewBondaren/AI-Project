from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
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
    level: str = Query(default="skeleton", pattern="^(registry|skeleton)$"),
    container=Depends(get_container),
) -> JSONResponse:
    bundle = await container.world_bundle_service().export(world_uid, level=level)  # type: ignore[arg-type]
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
    # TODO(WP-DELETE-1): DELETE world is not FK-safe / not atomic.
    # Symptom (smoke 2026-07-19): sqlite3.IntegrityError FOREIGN KEY constraint failed → HTTP 500.
    # Cause: child tables reference worlds(world_uid) without ON DELETE CASCADE; service deletes
    # only the worlds row. Partial purge (e.g. locations first) → half-deleted world on FK fail.
    # Tech debt: docs/tz_generator_technical_debt.md § WP-DELETE-1;
    #            docs/tz_world_pack_storage.md § WP-FIX-DEBT-10.
    await container.world_service().delete(world_uid)


@router.post("/worlds/import")
async def import_world(
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    level: str = Query(default="skeleton", pattern="^(registry|skeleton)$"),
    container=Depends(get_container),
) -> JSONResponse:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="World bundle JSON must be an object")
    results, rolled_back = await container.world_bundle_service().import_bundle(
        data, level=level,  # type: ignore[arg-type]
    )
    content = {k: v.to_dict() for k, v in results.items()}
    if rolled_back:
        failed_sections = [k for k, v in results.items() if v.failed > 0]
        content["rolled_back"] = True
        content["rollback_reason"] = f"failures in: {', '.join(failed_sections)}"
        status_code = 207
    else:
        status_code = 200
    return JSONResponse(status_code=status_code, content=content)


@router.post("/worlds/{world_uid}/pack/import")
async def import_world_pack(
    world_uid: str,
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    import tempfile
    from pathlib import Path

    from app.application.worldData.pack.import_.packImportService import PackImportService

    world = await container.world_service().get_by_id(world_uid)
    if world is None:
        raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

    if file is not None:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(await file.read())
            zip_path = Path(tmp.name)
    elif path:
        zip_path = Path(path)
    else:
        raise HTTPException(status_code=422, detail="Provide file or path")

    paths = container.world_pack_paths_for(world)
    try:
        result = PackImportService().import_zip(paths, zip_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if file is not None:
            zip_path.unlink(missing_ok=True)

    return JSONResponse(status_code=200, content=result)
