from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_container
from app.application.worldData.gameSessionService import GameSessionService

router = APIRouter()


class CreateSessionRequest(BaseModel):
    world_uid: str
    character_id: str


def get_session_service(container=Depends(get_container)):
    return container.game_session_service()


@router.get("/sessions")
async def list_sessions(service: GameSessionService = Depends(get_session_service)):
    return [asdict(s) for s in await service.list_all()]


@router.post("/sessions", status_code=201)
async def create_session(
    data: CreateSessionRequest,
    service: GameSessionService = Depends(get_session_service),
):
    session = await service.create(data.world_uid, data.character_id)
    return asdict(session)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    service: GameSessionService = Depends(get_session_service),
):
    return asdict(await service.get_by_id(session_id))
