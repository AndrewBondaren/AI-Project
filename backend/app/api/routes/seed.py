from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.api.utils.responseHelpers import json_or_download

router = APIRouter()


@router.post("/seed/import")
async def import_seed(
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Seed JSON must be an object keyed by table name")
    results = await container.seed_service().import_from_json(data)
    has_failures = any(r.failed > 0 for r in results.values())
    status_code = 207 if has_failures else 200
    return JSONResponse(
        status_code=status_code,
        content={table: r.to_dict() for table, r in results.items()},
    )


@router.get("/seed/export")
async def export_seed(
    download: bool = False,
    container=Depends(get_container),
) -> JSONResponse:
    data = await container.seed_service().export_all()
    return json_or_download(data, download, "seed.json")


@router.get("/seed/{table}")
async def list_seed(table: str, container=Depends(get_container)) -> list[dict]:
    return await container.seed_service().get_all(table)


@router.post("/seed/{table}", status_code=201)
async def upsert_seed(
    table: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    await container.seed_service().upsert_one(table, data)
    return {"ok": True}


@router.delete("/seed/{table}/{pk_val}", status_code=204)
async def delete_seed(
    table: str,
    pk_val: str,
    container=Depends(get_container),
) -> None:
    await container.seed_service().delete_one(table, pk_val)
