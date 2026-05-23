import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.db.models.gameSession import GameSession
from app.db.models.sessionSummary import SessionSummary
from app.db.repositories.iSessionRepository import ISessionRepository
from app.db.repositories.iWorldRepository import IWorldRepository
from app.db.repositories.iPlayerRepository import IPlayerRepository


class GameSessionService:

    def __init__(
        self,
        repo: ISessionRepository,
        world_repo: IWorldRepository,
        player_repo: IPlayerRepository,
    ) -> None:
        self._repo = repo
        self._world_repo = world_repo
        self._player_repo = player_repo

    async def list_all(self) -> list[SessionSummary]:
        return await self._repo.get_all_enriched()

    async def get_by_id(self, session_id: str) -> GameSession:
        session = await self._repo.get_by_id(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        return session

    async def create(self, world_uid: str, character_id: str) -> GameSession:
        world = await self._world_repo.get_by_id(world_uid)
        if world is None:
            raise HTTPException(status_code=404, detail=f"World '{world_uid}' not found")

        player = await self._player_repo.get_by_id(character_id)
        if player is None:
            raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")
        if player.world_uid != world_uid:
            raise HTTPException(status_code=400, detail="Character does not belong to this world")

        existing = await self._repo.get_by_world_and_character(world_uid, character_id)
        if existing:
            return existing

        now = datetime.now(timezone.utc).isoformat()
        session = GameSession(
            id=str(uuid.uuid4()),
            world_uid=world_uid,
            player_character_id=character_id,
            created_at=now,
            last_active_at=now,
        )
        await self._repo.create(session)
        return session
