from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.chat.chatService import ChatService
from app.application.chat.session import Session
from app.api.deps import get_container


router = APIRouter()

class ChatRequest(BaseModel):
    llm_provider: str
    model: str
    user_id: str
    meta: dict
    message: str

#TODO later
class ChatSettings(BaseModel):
    max_tokens: int
    repair_iterations: int
    language: str
    max_passes: int

class ChatResponse(BaseModel):
    response: str


def get_chat_service(container = Depends(get_container)):
    return container.chat_service()

@router.get("/health")
def health():
    return {
        "status": "ok"
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    service: ChatService = Depends(get_chat_service)
):
    session = Session(
        llm_provider=data.llm_provider,
        model=data.model,
        user_id=data.user_id,
        meta={}, #meta=data.meta
#        max_tokens=data.max_tokens, #вынести в запрос настроек
#        repair_iterations=data.repair_iterations, #вынести в запрос настроек
#        max_passes=data.max_passes #вынести в запрос настроек
    )
    result = await service.handle_message(
        session=session,
        message=data.message
    )

    return ChatResponse(response=result)