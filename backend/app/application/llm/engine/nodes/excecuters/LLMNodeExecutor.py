class LLMNodeExecutor:

    async def execute(self, node, state, context):

        contract = node.contract

        prompt_builder = context.prompt_builder_registry

        messages = prompt_builder.build(
            message=state.message,
            contract_model=contract
        )

        client = context.router.get(state.session.llm_provider)

        return await context.executors.structured.execute(
            node=node,
            state=state,
            client=client,
            model=state.session.llm_model,
            messages=messages,
            contract=contract,
        )