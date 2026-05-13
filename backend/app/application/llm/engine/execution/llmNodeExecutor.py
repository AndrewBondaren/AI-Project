class LLMNodeExecutor:

    def __init__(self, router):
        self.router = router

    async def execute(self, node, state, context):

        client = self.router.get(state.session.llm_provider)

        result = await client.chat(
            model=node.model,
            messages=node.messages  # или уже готовые
        )

        return result