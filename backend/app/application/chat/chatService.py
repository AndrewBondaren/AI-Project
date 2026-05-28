import asyncio
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from app.application.chat.session import Session
from app.application.engine.taskType import TaskType
from app.db.models.message import Message, Turn
from app.db.repositories.iMessageRepository import IMessageRepository
from app.db.repositories.iPendingRepository import IPendingRepository


class ChatService:

    def __init__(self, llm_engine, message_repo: IMessageRepository, pending_repo: IPendingRepository):
        self.engine = llm_engine
        self._message_repo = message_repo
        self._pending_repo = pending_repo

    async def handle_message(self, session: Session, message: str, cancel_token=None, snapshot=None, task_type: str | None = None):
        if snapshot is None:
            await self._pending_repo.upsert(session.session_id, message)

        resolved_task_type = TaskType(task_type) if task_type else TaskType.INTENT_DETECTION

        try:
            result = await self.engine.run(
                task_type=resolved_task_type,
                message=message,
                session=session,
                cancel_token=cancel_token,
                snapshot=snapshot,
            )
        except asyncio.CancelledError:
            snap = self.engine.snapshot_store.load(session.session_id)
            if snap:
                try:
                    await self._pending_repo.update_snapshot(
                        session.session_id, json.dumps(asdict(snap))
                    )
                except (TypeError, ValueError):
                    pass  # player_input stays in pending without snapshot
            raise

        if not (isinstance(result, dict) and result.get("ok") is False):
            await self._save_turn(session.session_id, message, result)
            await self._pending_repo.delete(session.session_id)

        return result

    async def _save_turn(self, session_id: str, player_input: str, result) -> None:
        turn_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        llm_text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        await self._message_repo.create_turn(Turn(
            turn_id=turn_id,
            session_id=session_id,
            player_input=player_input,
            created_at=now,
        ))
        await self._message_repo.create_message(Message(
            message_id=str(uuid.uuid4()),
            turn_id=turn_id,
            session_id=session_id,
            created_at=now,
            message_type='narrative',
            llm_output=llm_text,
        ))
