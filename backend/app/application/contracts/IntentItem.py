from pydantic import BaseModel
from backend.app.application.engine.taskType import TaskType

class IntentItem(BaseModel):
    task_type: TaskType
    confidence: float