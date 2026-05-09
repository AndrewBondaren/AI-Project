# application/llm/llm_orchestrator.py

from backend.infrastructure.llm.router import LLMRouter
from backend.application.llm.prompt_builder import PromptBuilder
from backend.application.llm.response_parser import LLMResponseParser
from backend.core.config import settings


class LLMOrchestrator:

    def __init__(self):
        self.llm = LLMRouter()
        self.prompts = PromptBuilder()
        self.parser = LLMResponseParser()

    async def narrate_combat(self, combat_result, character):

        messages = self.prompts.build_combat_prompt(
            combat_result,
            character
        )

        response = await self.llm.chat(
            provider=settings.LLM_PROVIDER,  # ← qwen
            messages=messages,
            model="qwen-3.6"
        )

        return self.parser.extract_text(response)

    async def chat(self, message, context):

        messages = self.prompts.build_chat_prompt(
            message,
            context
        )

        response = await self.llm.chat(
            provider=settings.LLM_PROVIDER,
            messages=messages,
            model="qwen-3.6"
        )

        return self.parser.extract_text(response)