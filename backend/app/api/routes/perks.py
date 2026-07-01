from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.crudPatchGate import gate_entity_create, gate_entity_update
from app.api.utils.jsonResolver import JsonResolver
from app.api.utils.sectionImportGate import gate_section_import
from app.application.worldData.jsonValidation.types import SectionKey

router = APIRouter()


@router.get("/worlds/{world_uid}/perks")
async def list_perks(world_uid: str, container=Depends(get_container)) -> list[dict]:
    perks = await container.perk_service().get_all(world_uid)
    return [asdict(p) for p in perks]


@router.get("/worlds/{world_uid}/perks/{perk_uid}")
async def get_perk(world_uid: str, perk_uid: str, container=Depends(get_container)) -> dict:
    perk = await container.perk_service().get_by_id(world_uid, perk_uid)
    return asdict(perk)


@router.post("/worlds/{world_uid}/perks", status_code=201)
async def create_perk(
    world_uid: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    row = await gate_entity_create(container, world_uid, SectionKey.PERKS, data)
    perk = await container.perk_service().create(world_uid, row)
    return asdict(perk)


@router.put("/worlds/{world_uid}/perks/{perk_uid}")
async def update_perk(
    world_uid: str,
    perk_uid: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    row = await gate_entity_update(
        container,
        world_uid,
        SectionKey.PERKS,
        perk_uid,
        data,
        load_existing=container.perk_service().get_by_id,
        immutable=frozenset({"perk_uid", "world_uid"}),
    )
    perk = await container.perk_service().update(world_uid, perk_uid, row)
    return asdict(perk)


@router.delete("/worlds/{world_uid}/perks/{perk_uid}", status_code=204)
async def delete_perk(
    world_uid: str,
    perk_uid: str,
    container=Depends(get_container),
) -> None:
    await container.perk_service().delete(world_uid, perk_uid)


@router.post("/worlds/{world_uid}/perks/import")
async def import_perks(
    world_uid: str,
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, list):
        raise HTTPException(status_code=422, detail="Perks JSON must be an array")
    data = await gate_section_import(
        container,
        world_uid=world_uid,
        section=SectionKey.PERKS,
        payload=data,
    )
    result = await container.perk_service().import_from_json(world_uid, data)
    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())
