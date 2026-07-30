"""HTTP thin layer for global relief_templates library — tz_terrain_relief R29."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.application.worldData.reliefErrors import ReliefNotFoundError, ReliefValidationError
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)

router = APIRouter()


def _http_from_relief(exc: Exception) -> HTTPException:
    if isinstance(exc, ReliefNotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, ReliefValidationError):
        return HTTPException(status_code=422, detail=exc.message)
    raise exc


@router.get("/relief-templates")
async def list_relief_templates(container=Depends(get_container)) -> list[dict]:
    rows = await container.relief_template_library_service().list_all()
    return [ReliefTemplateLibraryService.row_as_dict(r) for r in rows]


@router.get("/relief-templates/{template_uid}")
async def get_relief_template(template_uid: str, container=Depends(get_container)) -> dict:
    try:
        row = await container.relief_template_library_service().get_by_uid(template_uid)
    except ReliefNotFoundError as exc:
        raise _http_from_relief(exc) from exc
    return ReliefTemplateLibraryService.row_as_dict(row)


@router.post("/relief-templates", status_code=201)
async def upsert_relief_template(
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    try:
        row = await container.relief_template_library_service().upsert_from_dict(data)
    except (ReliefNotFoundError, ReliefValidationError) as exc:
        raise _http_from_relief(exc) from exc
    return ReliefTemplateLibraryService.row_as_dict(row)


@router.post("/relief-templates/import")
async def import_relief_templates(
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    """Import one JSON object, a JSON array of outlines, or a filesystem pack path."""
    svc = container.relief_template_library_service()
    try:
        if path:
            rows = await svc.import_path(path)
            return JSONResponse(
                status_code=200,
                content={"imported": len(rows), "uids": [r.template_uid for r in rows]},
            )
        data = await JsonResolver.resolve(file=file, path=None)
        if isinstance(data, dict):
            row = await svc.upsert_from_dict(data)
            return JSONResponse(
                status_code=200,
                content={"imported": 1, "uids": [row.template_uid]},
            )
        if isinstance(data, list):
            uids: list[str] = []
            for item in data:
                if not isinstance(item, dict):
                    raise HTTPException(status_code=422, detail="Array items must be objects")
                row = await svc.upsert_from_dict(item)
                uids.append(row.template_uid)
            return JSONResponse(status_code=200, content={"imported": len(uids), "uids": uids})
    except (ReliefNotFoundError, ReliefValidationError) as exc:
        raise _http_from_relief(exc) from exc
    raise HTTPException(status_code=422, detail="Expected object, array, or path")


@router.post("/worlds/{world_uid}/relief-templates/import")
async def import_relief_into_world(
    world_uid: str,
    data: dict[str, Any] | list[Any] | None = None,
    template_uid: str | None = None,
    container=Depends(get_container),
) -> JSONResponse:
    """Import library uid or outline body(ies) into world registry (+ R34 terrain sync)."""
    svc = container.relief_world_import_service()
    try:
        if template_uid:
            result = await svc.import_library_uid_into_world(world_uid, template_uid)
            return JSONResponse(status_code=200, content=result)
        body = data
        if body is None:
            raise HTTPException(status_code=422, detail="Provide template_uid or JSON body")
        if isinstance(body, dict):
            if "template_uid" in body and len(body) == 1:
                result = await svc.import_library_uid_into_world(world_uid, body["template_uid"])
                return JSONResponse(status_code=200, content=result)
            outlines = [body]
        elif isinstance(body, list):
            outlines = body
        else:
            raise HTTPException(status_code=422, detail="Expected object or array")
        result = await svc.import_outlines_into_world(world_uid, outlines)
        return JSONResponse(status_code=200, content=result)
    except (ReliefNotFoundError, ReliefValidationError) as exc:
        raise _http_from_relief(exc) from exc


@router.delete("/relief-templates/{template_uid}", status_code=204)
async def delete_relief_template(template_uid: str, container=Depends(get_container)) -> None:
    try:
        await container.relief_template_library_service().delete(template_uid)
    except ReliefNotFoundError as exc:
        raise _http_from_relief(exc) from exc
