import json
from pydantic import BaseModel


class LLMNodeExecutor:

    def __init__(self, router):
        self.router = router

    async def execute(self, node, state, context):

        client = self.router.get(state.session.llm_provider)

        raw = await client.chat(
            model=node.model,
            messages=context.get("messages", [])  # временно из context
        )

        # десериализация
        if node.contract_json:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                return node.contract_json.model_validate(data)
            except Exception as e:
                # возвращаем сырой результат — ContractValidator поймает
                return raw

        return raw