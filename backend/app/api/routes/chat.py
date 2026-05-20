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
from app.application.events.sseEvents import ResultEvent, ErrorEvent


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
    user_id: str
    meta: dict
    message: str

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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    service: ChatService = Depends(get_chat_service)
):
    session = Session(
        llm_provider=data.llm_provider,
        model=data.model,
        user_id=data.user_id,
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
        user_id=data.user_id,
        meta=data.meta,
    )
    queue = init_bus()

    async def run_pipeline():
        try:
            result = await service.handle_message(session=session, message=data.message)
            if isinstance(result, dict) and result.get("ok") is False:
                await emit(ErrorEvent(message=result.get("error", "Unknown error")))
            else:
                await emit(ResultEvent(response=result))
        except UserInputError as e:
            await emit(ErrorEvent(message=e.message))
        except Exception as e:
            await emit(ErrorEvent(message=str(e)))
        finally:
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