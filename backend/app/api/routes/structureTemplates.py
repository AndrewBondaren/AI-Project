"""HTTP thin layer for global structure_templates library (5o split, model A)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import get_container
from app.application.worldData.structureTemplateErrors import (
    StructureTemplateNotFoundError,
    StructureTemplateValidationError,
)
from app.application.worldData.structureTemplateLibraryService import (
    StructureTemplateLibraryService,
)
from app.db.models.structureTemplate import StructureTemplateRow

router = APIRouter()


class _ImportPath(BaseModel):
    path: str


def _http_from_structure(exc: Exception) -> HTTPException:
    if isinstance(exc, StructureTemplateNotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, StructureTemplateValidationError):
        return HTTPException(status_code=422, detail=exc.message)
    raise exc


def _summary(row: StructureTemplateRow) -> dict:
    data = row.data if isinstance(row.data, dict) else {}
    return {
        "template_uid": row.template_uid,
        "display_name": row.display_name,
        "version": row.version,
        "structure_types": data.get("structure_types") or [],
    }


@router.get("/structure-templates")
async def list_structure_templates(container=Depends(get_container)) -> list[dict]:
    rows = await container.structure_template_library_service().list_all()
    return [_summary(r) for r in rows]


@router.get("/structure-templates/{template_uid}")
async def get_structure_template(
    template_uid: str, container=Depends(get_container),
) -> dict:
    try:
        row = await container.structure_template_library_service().get_by_uid(template_uid)
    except StructureTemplateNotFoundError as exc:
        raise _http_from_structure(exc) from exc
    return StructureTemplateLibraryService.row_as_dict(row)


@router.post("/structure-templates", status_code=201)
async def upsert_structure_template(
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    try:
        row = await container.structure_template_library_service().upsert_from_dict(data)
    except (StructureTemplateNotFoundError, StructureTemplateValidationError) as exc:
        raise _http_from_structure(exc) from exc
    return StructureTemplateLibraryService.row_as_dict(row)


@router.post("/structure-templates/import")
async def import_structure_templates(
    body: _ImportPath,
    container=Depends(get_container),
) -> JSONResponse:
    """Import a JSON file or pack directory resolved under structures_templates/."""
    svc = container.structure_template_library_service()
    try:
        rows = await svc.import_path(body.path)
    except (StructureTemplateNotFoundError, StructureTemplateValidationError) as exc:
        raise _http_from_structure(exc) from exc
    return JSONResponse(
        status_code=200,
        content={"imported": len(rows), "uids": [r.template_uid for r in rows]},
    )


@router.delete("/structure-templates/{template_uid}", status_code=204)
async def delete_structure_template(
    template_uid: str, container=Depends(get_container),
) -> None:
    try:
        await container.structure_template_library_service().delete(template_uid)
    except StructureTemplateNotFoundError as exc:
        raise _http_from_structure(exc) from exc
