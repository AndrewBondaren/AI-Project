"""HTTP thin layer for global relief_templates library — tz_terrain_relief R29."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.jsonResolver import JsonResolver
from app.api.libraryWrite import parse_negotiation
from app.application.templateLibrary.packs.errors import require_no_policy
from app.ids import LibraryKind
from app.application.templateLibrary.reliefErrors import ReliefNotFoundError, ReliefValidationError
from app.application.templateLibrary.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)

router = APIRouter()


def _http_from_relief(exc: Exception) -> HTTPException:
    if isinstance(exc, ReliefNotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, ReliefValidationError):
        return HTTPException(status_code=422, detail=exc.message)
    raise exc


async def _instantiate_member_pack(
    container, world_uid: str, template_uid: str, *, decisions=(), preview_token=None,
) -> dict:
    """``template_uid`` → owning engine pack → ``instantiate_pack`` (TZ §1.1)."""
    packs = container.library_pack_service()
    member = await packs.get_member(template_uid)
    res = require_no_policy(await packs.instantiate_pack_negotiated(member.pack_uid,
        world_uid=world_uid, decisions=decisions, preview_token=preview_token))
    return {
        "pack_uid": res.pack.pack_uid,
        "created": res.created,
        "imported": len(res.members),
        "uids": [m.template_uid for m in res.members],
        "missing_dependencies": list(res.missing_dependencies),
    }


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
    pack_uid: str | None = None,
    negotiation=Depends(parse_negotiation),
) -> dict:
    try:
        result = require_no_policy(await container.library_pack_service().write_authored_bodies(
            LibraryKind.RELIEF_TEMPLATES, pack_uid, [data],
            decisions=negotiation.decisions, preview_token=negotiation.preview_token))
        uid = result.plan.items[0].members[0].value.member.template_uid
        row = await container.relief_template_library_service().get_by_uid(uid)
    except (ReliefNotFoundError, ReliefValidationError) as exc:
        raise _http_from_relief(exc) from exc
    return ReliefTemplateLibraryService.row_as_dict(row)


@router.post("/relief-templates/import")
async def import_relief_templates(
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
    pack_uid: str | None = Form(default=None),
    decisions: str | None = Form(default=None),
    preview_token: str | None = Form(default=None),
) -> JSONResponse:
    """Import one JSON object, a JSON array of outlines, or a filesystem pack path."""
    svc = container.relief_template_library_service()
    negotiation = parse_negotiation(decisions, preview_token)
    options = {"decisions": negotiation.decisions, "preview_token": negotiation.preview_token}
    try:
        if path:
            rows = require_no_policy(await svc.import_path(path, **options))
            return JSONResponse(
                status_code=200,
                content={"imported": len(rows), "uids": [r.template_uid for r in rows]},
            )
        data = await JsonResolver.resolve(file=file, path=None)
        if isinstance(data, (dict, list)):
            result = require_no_policy(await container.library_pack_service().write_authored_bodies(
                LibraryKind.RELIEF_TEMPLATES, pack_uid, [data] if isinstance(data, dict) else data,
                source_file="upload", **options))
            uids = [w.value.member.template_uid for item in result.plan.items for w in item.members]
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
    negotiation=Depends(parse_negotiation),
) -> JSONResponse:
    """Instantiate the pack owning ``template_uid`` into the world."""
    uid = template_uid
    if uid is None and isinstance(data, dict) and set(data) == {"template_uid"}:
        uid = data["template_uid"]
    if uid is None:
        raise HTTPException(
            status_code=422,
            detail="Provide template_uid; loose outline bodies are not accepted",
        )
    result = await _instantiate_member_pack(container, world_uid, uid,
        decisions=negotiation.decisions, preview_token=negotiation.preview_token)
    return JSONResponse(status_code=200, content=result)


@router.delete("/relief-templates/{template_uid}", status_code=204)
async def delete_relief_template(template_uid: str, container=Depends(get_container)) -> None:
    try:
        await container.relief_template_library_service().delete(template_uid)
    except ReliefNotFoundError as exc:
        raise _http_from_relief(exc) from exc
