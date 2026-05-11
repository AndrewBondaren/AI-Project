from app.application.llm.response.taskType import TaskType

class ChatService:

    def __init__(self, llm_engine):
        self.engine = llm_engine

    async def handle_message(self, session_id: str, message: str):

        result = await self.engine.run(
            task_type = TaskType.CHAT,
            message=message,
            session_id=session_id
        )

        return result