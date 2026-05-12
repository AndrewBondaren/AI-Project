from app.application.llm.engine.taskType import TaskType

class ChatService:

    def __init__(self, llm_engine):
        self.engine = llm_engine

    async def handle_message(self, session: str, message: str):

        result = await self.engine.run(
            task_type = TaskType.CHAT,
            message=message,
            session=session
        )

        return result