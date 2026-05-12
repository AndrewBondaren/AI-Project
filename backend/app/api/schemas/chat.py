from pydantic import BaseModel
from typing import Any


class ChatRequest(BaseModel):
    session: str
    message: str


class SocketEvent(BaseModel):
    type: str
    payload: Any