from typing import Any
import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.application.chat.chatService import ChatService
from app.application.chat.session import Session
from app.application.engine.errors import UserInputError
from app.application.engine.repair.repairMode import RepairMode
from app.application.llm.language import Language
from app.core.appSettings import app_settings
from app.api.deps import get_container
from app.application.events.eventBus import init_bus, emit, close_bus
from app.application.events.sseEvents import ResultEvent, ErrorEvent, CancelledEvent
from app.application.cancellation.cancellationToken import CancellationToken
from app.application.cancellation.cancellationRegistry import cancellation_registry
from app.application.cancellation.snapshotStore import snapshot_store


router = APIRouter()


class ChatSettings(BaseModel):
    max_tokens:        int
    repair_iterations: int
    repair_mode:       RepairMode
    language:          Language
    max_passes:        int


class ChatRequest(BaseModel):
    llm_provider: str
    model: str
    session_id: str
    meta: dict
    message: str
    request_id: str
    resume: bool = False

class ChatResponse(BaseModel):
    ok: bool = True
    response: Any = None
    error: str | None = None


def get_chat_service(container = Depends(get_container)):
    return container.chat_service()

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/chat/settings")
def get_chat_settings() -> ChatSettings:
    return ChatSettings(
        max_tokens=app_settings.max_tokens,
        repair_iterations=app_settings.repair_iterations,
        repair_mode=app_settings.repair_mode,
        language=app_settings.language,
        max_passes=app_settings.max_passes,
    )


@router.put("/chat/settings")
def update_chat_settings(data: ChatSettings) -> ChatSettings:
    app_settings.update(
        max_tokens=data.max_tokens,
        repair_iterations=data.repair_iterations,
        repair_mode=data.repair_mode,
        language=data.language,
        max_passes=data.max_passes,
    )
    return get_chat_settings()


@router.delete("/chat/stream/{request_id}")
async def cancel_stream(request_id: str):
    cancellation_registry.cancel(request_id)
    return {"ok": True}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    service: ChatService = Depends(get_chat_service)
):
    session = Session(
        llm_provider=data.llm_provider,
        model=data.model,
        session_id=data.session_id,
        meta=data.meta,
    )
    try:
        result = await service.handle_message(
            session=session,
            message=data.message
        )
    except UserInputError as e:
        return ChatResponse(ok=False, error=e.message)

    if isinstance(result, dict) and result.get("ok") is False:
        return ChatResponse(ok=False, error=result.get("error"), response=result)

    return ChatResponse(ok=True, response=result)


@router.post("/chat/stream")
async def chat_stream(
    data: ChatRequest,
    service: ChatService = Depends(get_chat_service)
):
    session = Session(
        llm_provider=data.llm_provider,
        model=data.model,
        session_id=data.session_id,
        meta=data.meta,
    )

    # Resolve snapshot for resume / clear for new request
    if data.resume:
        snapshot = snapshot_store.load(data.session_id)
        if snapshot is None:
            async def _error_gen():
                yield f"data: {ErrorEvent(message='No snapshot found for session_id').model_dump_json()}\n\n"
            return StreamingResponse(
                _error_gen(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
    else:
        snapshot_store.delete(data.session_id)
        snapshot = None

    token = CancellationToken(request_id=data.request_id)
    cancellation_registry.register(token)

    queue = init_bus()

    async def run_pipeline():
        try:
            result = await service.handle_message(
                session=session,
                message=data.message,
                cancel_token=token,
                snapshot=snapshot,
            )
            if isinstance(result, dict) and result.get("ok") is False:
                await emit(ErrorEvent(message=result.get("error", "Unknown error")))
            else:
                snapshot_store.delete(data.session_id)
                await emit(ResultEvent(response=result))
        except asyncio.CancelledError:
            await emit(CancelledEvent(session_id=data.session_id, request_id=data.request_id))
        except UserInputError as e:
            await emit(ErrorEvent(message=e.message))
        except Exception as e:
            await emit(ErrorEvent(message=str(e)))
        finally:
            cancellation_registry.remove(data.request_id)
            await close_bus()

    async def event_generator():
        task = asyncio.create_task(run_pipeline())
        try:
            while True:
                event = await queue.get()
                if event is None:  # sentinel — pipeline finished
                    break
                yield f"data: {event.model_dump_json()}\n\n"
        finally:
            await task  # surface any unhandled exceptions

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
