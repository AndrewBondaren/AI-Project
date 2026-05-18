from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


def normalize_messages(messages: list[Any]) -> list[ChatMessage]:
    normalized: list[ChatMessage] = []
    for message in messages:
        if isinstance(message, ChatMessage):
            normalized.append(message)
        elif isinstance(message, dict):
            normalized.append(ChatMessage(**message))
        else:
            normalized.append(ChatMessage(role=message.role, content=message.content))
    return normalized


class LLMResponse(BaseModel):

    text: str
    data: Dict[str, Any] = Field(default_factory=dict)
    raw: str = ""


class ValidationError(BaseModel):
    rule: str
    message: str


class ValidationResult(BaseModel):
    success: bool
    errors: List[ValidationError] = Field(default_factory=list)