from typing import Dict, Any, List
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


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