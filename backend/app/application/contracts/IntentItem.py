from enum import Enum

from pydantic import BaseModel

from app.application.engine.taskType import TaskType

LLMTaskType = Enum(
    "LLMTaskType",
    {t.name: t.value for t in TaskType if not t.is_technical},
    type=str,
)


class IntentItem(BaseModel):
    task_type: LLMTaskType  # type: ignore[valid-type]
    confidence: float
