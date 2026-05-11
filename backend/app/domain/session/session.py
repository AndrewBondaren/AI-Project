from pydantic import BaseModel, Field
from typing import List

from app.application.llm.models import ChatMessage


class LLMSession(BaseModel):

    id: str

    messages: List[ChatMessage] = Field(default_factory=list)

    retry_count: int = 0

    validator_state: dict = Field(default_factory=dict)