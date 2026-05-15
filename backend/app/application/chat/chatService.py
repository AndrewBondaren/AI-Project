from app.application.engine.taskType import TaskType
from app.application.chat.session import Session

class ChatService:

    def __init__(self, llm_engine):
        self.engine = llm_engine

    async def handle_message(self, session: Session, message: str):

        result = await self.engine.run(
            task_type = TaskType.CHAT,
            message=message,
            session=session
        )

        return result