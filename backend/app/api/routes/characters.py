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
    world_uid: str | None = Form(default=None),
    container=Depends(get_container),
):
    data = await JsonResolver.resolve(file=file, path=path)

    from app.application.character.jsonValidation.contextLoader import load_world_validation_context
    from app.application.worldData.jsonValidation import format_validation_issues
    from app.application.worldData.jsonValidation.types import ValidationKind, ValidationRequest

    req = ValidationRequest(kind=ValidationKind.CHARACTER, payload=data)
    if world_uid:
        ctx = await load_world_validation_context(
            world_service=container.world_service(),
            race_service=container.race_service(),
            location_service=container.location_service(),
            seed_service=container.seed_service(),
            world_uid=world_uid,
        )
        req = ValidationRequest(kind=ValidationKind.CHARACTER, payload=data, **ctx)

    validation = await container.json_validation_facade().validate(req)
    if not validation.ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=format_validation_issues(validation))

    payload = validation.normalized if isinstance(validation.normalized, dict) else data
    return asdict(await container.player_service().create(payload))


@router.get("/characters")
async def list_characters(service: PlayerService = Depends(get_player_service)):
    return await service.get_all()


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


@router.post("/characters/{character_uid}/copy", status_code=201)
async def copy_character(
    character_uid: str,
    service: PlayerService = Depends(get_player_service),
):
    player = await service.copy(character_uid)
    return asdict(player)


@router.delete("/characters/{character_uid}", status_code=204)
async def delete_character(
    character_uid: str,
    service: PlayerService = Depends(get_player_service),
):
    await service.delete(character_uid)
