from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_container
from app.api.utils.json_resolver import JsonResolver

router = APIRouter()


@router.get("/worlds/{world_id}/races")
async def list_races(world_id: str, container=Depends(get_container)) -> list[dict]:
    races = await container.race_service().get_all(world_id)
    return [asdict(r) for r in races]


@router.get("/worlds/{world_id}/races/{race_uid}")
async def get_race(world_id: str, race_uid: str, container=Depends(get_container)) -> dict:
    race = await container.race_service().get_by_id(world_id, race_uid)
    return asdict(race)


@router.post("/worlds/{world_id}/races", status_code=201)
async def create_race(
    world_id: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    race = await container.race_service().create(world_id, data)
    return asdict(race)


@router.put("/worlds/{world_id}/races/{race_uid}")
async def update_race(
    world_id: str,
    race_uid: str,
    data: dict[str, Any],
    container=Depends(get_container),
) -> dict:
    race = await container.race_service().update(world_id, race_uid, data)
    return asdict(race)


@router.delete("/worlds/{world_id}/races/{race_uid}", status_code=204)
async def delete_race(
    world_id: str,
    race_uid: str,
    container=Depends(get_container),
) -> None:
    await container.race_service().delete(world_id, race_uid)


@router.post("/worlds/{world_id}/races/import")
async def import_races(
    world_id: str,
    file: UploadFile | None = File(default=None),
    path: str | None = Form(default=None),
    container=Depends(get_container),
) -> JSONResponse:
    data = await JsonResolver.resolve(file=file, path=path)
    if not isinstance(data, list):
        raise HTTPException(status_code=422, detail="Races JSON must be an array")
    result = await container.race_service().import_from_json(world_id, data)
    status_code = 200 if result.failed == 0 else 207
    return JSONResponse(status_code=status_code, content=result.to_dict())
