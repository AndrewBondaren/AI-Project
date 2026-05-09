# application/chat/chat_service.py

from application.chat.stateBuilder import StateBuilder
from application.llm.promptBuilder import PromptBuilder
from application.llm.responseParser import ResponseParser


class ChatService:
    def __init__(self, llm_router):
        self.llm = llm_router
        self.state_builder = StateBuilder()
        self.prompt_builder = PromptBuilder()
        self.parser = ResponseParser()

    async def handle_message(self, session_id: str, message: str):

        # 1. собрать state (перс, сессия, мир)
        state = self.state_builder.build(session_id, message)

        # 2. собрать prompt
        prompt = self.prompt_builder.build(state)

        # 3. вызвать LLM
        raw_response = await self.llm.generate(prompt)

        # 4. распарсить ответ
        parsed = self.parser.parse(raw_response)

        return parsed.get("text", "...")