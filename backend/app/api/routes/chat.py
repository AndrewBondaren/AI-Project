from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.chat.chatService import ChatService
from app.api.deps import get_container


router = APIRouter()

class ChatRequest(BaseModel):
    session: str
    message: str


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
    print("CHAT ENDPOINT HIT"),
    result = await service.handle_message(
        session=data.session,
        message=data.message
    )

    return ChatResponse(response=result)