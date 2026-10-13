"""Thin scoped library lifecycle routes; shared negotiation (TZ §0.2/0.3/4)."""
from dataclasses import asdict

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.api.deps import get_container
from app.api.libraryWrite import WriteNegotiation, policy_response, write_response
from app.application.worldData.libraryPacks.writeResults import PolicyRequired

router = APIRouter()


class PackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system_name: str
    pack_name: str | None = None
    display_name: str | None = None
    version: str = "1.0"
    dependencies: tuple[str, ...] = ()


class PackEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack_name: str | None = None
    display_name: str | None = None
    version: str | None = None


class PackInstantiate(WriteNegotiation):
    source_pack_uid: str


class Publish(WriteNegotiation):
    system_name: str | None = None


class MemberCreate(WriteNegotiation):
    library_kind: str
    local_uid: str
    body: dict


class MemberCopy(WriteNegotiation):
    source_template_uid: str


@router.get("/library-packs")
@router.get("/worlds/{world_uid}/library-packs")
async def list_packs(world_uid: str | None = None, container=Depends(get_container)):
    service = container.library_pack_service()
    rows = await service.list_world_packs(world_uid) if world_uid else await service.list_engine_packs()
    return [asdict(row) for row in rows]


@router.post("/library-packs", status_code=201)
@router.post("/worlds/{world_uid}/library-packs", status_code=201)
async def create_pack(body: PackCreate, world_uid: str | None = None, container=Depends(get_container)):
    return asdict(await container.library_pack_service().create_pack(
        **body.model_dump(), owner_world_uid=world_uid))


@router.post("/worlds/{world_uid}/library-packs/instantiate")
async def instantiate(world_uid: str, body: PackInstantiate, container=Depends(get_container)):
    result = await container.library_pack_service().instantiate_pack_negotiated(body.source_pack_uid,
        world_uid=world_uid, decisions=body.decisions, preview_token=body.preview_token)
    return policy_response(result) if isinstance(result, PolicyRequired) else jsonable_encoder(result)


@router.get("/library-packs/{pack_uid}")
async def get_pack(pack_uid: str, container=Depends(get_container)):
    return asdict(await container.library_pack_service().get_pack(pack_uid))


@router.patch("/library-packs/{pack_uid}")
@router.patch("/worlds/{world_uid}/library-packs/{pack_uid}")
async def edit_pack(pack_uid: str, body: PackEdit, world_uid: str | None = None, container=Depends(get_container)):
    return asdict(await container.library_pack_service().update_pack_metadata(
        pack_uid, **body.model_dump(exclude_unset=True), world_uid=world_uid))


@router.delete("/library-packs/{pack_uid}")
@router.delete("/worlds/{world_uid}/library-packs/{pack_uid}")
async def delete_pack(pack_uid: str, world_uid: str | None = None, container=Depends(get_container)):
    return jsonable_encoder(await container.library_pack_service().delete_pack(pack_uid, world_uid=world_uid))


@router.post("/worlds/{world_uid}/library-packs/{pack_uid}/publish")
async def publish(world_uid: str, pack_uid: str, body: Publish, container=Depends(get_container)):
    service = container.library_pack_service()
    pack = await service.get_pack(pack_uid)
    if pack.owner_world_uid != world_uid:
        from app.application.worldData.libraryPacks.errors import LibraryPackOwnershipError
        raise LibraryPackOwnershipError("publish source does not belong to the route world")
    result = await service.copy_pack(pack_uid, system_name=body.system_name,
                                     decisions=body.decisions, preview_token=body.preview_token)
    return policy_response(result) if isinstance(result, PolicyRequired) else jsonable_encoder(result)


@router.get("/library-packs/{pack_uid}/members")
async def list_members(pack_uid: str, container=Depends(get_container)):
    return [asdict(row) for row in await container.library_pack_service().list_members(pack_uid)]


@router.get("/library-members/{template_uid}")
async def get_member(template_uid: str, container=Depends(get_container)):
    service = container.library_pack_service()
    return {"member": asdict(await service.get_member(template_uid)),
            "body": await service.read_member_body(template_uid)}


@router.post("/library-packs/{pack_uid}/members")
@router.post("/worlds/{world_uid}/library-packs/{pack_uid}/members")
async def create_member(pack_uid: str, body: MemberCreate, world_uid: str | None = None,
                        container=Depends(get_container)):
    from app.ids import LibraryKind
    payload = dict(body.body)
    if body.library_kind != LibraryKind.STRUCTURE_TEMPLATES:
        payload.setdefault("system_name", body.local_uid)
    return write_response(await container.library_pack_service().write_authored_bodies(
        body.library_kind, pack_uid, [payload], local_uid=body.local_uid, world_uid=world_uid,
        decisions=body.decisions, preview_token=body.preview_token))


@router.post("/library-packs/{pack_uid}/members/copy")
@router.post("/worlds/{world_uid}/library-packs/{pack_uid}/members/copy")
async def copy_member(pack_uid: str, body: MemberCopy, world_uid: str | None = None,
                      container=Depends(get_container)):
    return write_response(await container.library_pack_service().copy_member_negotiated(
        body.source_template_uid, pack_uid, world_uid=world_uid,
        decisions=body.decisions, preview_token=body.preview_token))


@router.put("/library-members/{template_uid}")
@router.put("/worlds/{world_uid}/library-members/{template_uid}")
async def edit_member(template_uid: str, body: dict, world_uid: str | None = None, container=Depends(get_container)):
    return asdict(await container.library_pack_service().update_member_body(template_uid, body, world_uid=world_uid))


@router.delete("/library-members/{template_uid}")
@router.delete("/worlds/{world_uid}/library-members/{template_uid}")
async def delete_member(template_uid: str, world_uid: str | None = None, container=Depends(get_container)):
    return jsonable_encoder(await container.library_pack_service().delete_member(template_uid, world_uid=world_uid))
