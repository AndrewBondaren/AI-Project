from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_container
from app.api.utils.json_resolver import JsonResolver
from app.application.worldData.playerService import PlayerService

router = APIRouter()


def get_player_service(container=Depends(get_container)):
    return container.player_service()


@router.post("/characters/import", status_code=201)
async def import_character(
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    service: PlayerService = Depends(get_player_service),
):
    data = await JsonResolver.resolve(file=file, path=path)
    return asdict(await service.create(data))


@router.get("/characters")
async def list_characters(
    world_uid: str | None = None,
    service: PlayerService = Depends(get_player_service),
):
    players = await service.get_all(world_uid=world_uid)
    return [asdict(p) for p in players]


@router.get("/characters/{character_uid}")
async def get_character(
    character_uid: str,
    service: PlayerService = Depends(get_player_service),
):
    return asdict(await service.get_by_id(character_uid))


@router.post("/characters", status_code=201)
async def create_character(
    data: dict,
    service: PlayerService = Depends(get_player_service),
):
    return asdict(await service.create(data))


@router.delete("/characters/{character_uid}", status_code=204)
async def delete_character(
    character_uid: str,
    service: PlayerService = Depends(get_player_service),
):
    await service.delete(character_uid)
