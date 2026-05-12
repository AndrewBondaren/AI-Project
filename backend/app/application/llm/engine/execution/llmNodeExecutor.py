class LLMNodeExecutor:

    async def execute(self, node, state, context):

        if not node.dsl:
            raise ValueError(f"LLMNode {node.id} missing DSL")

        # 1. compile context
        prompt_context = context.prompt_compiler.compile(
            dsl=node.dsl,
            message=state.message,
            contract_schema=node.contract,   # лучше schema, но ок пока
            session=state.session,
            errors=getattr(state, "errors", None),
            world_state=getattr(state, "world", None),
        )

        # 2. resolve builder
        builder = context.prompt_builder_registry.get(node.dsl)

        # 3. build messages
        messages = builder.build(prompt_context)

        # 4. resolve client
        client = context.router.get(node.provider)

        if not client:
            raise ValueError(f"No LLM client for provider: {node.provider}")

        # 5. execute structured call
        result = await context.executors.structured.execute(
            node=node,
            state=state,
            client=client,
            model=node.model,
            messages=messages,
            temperature=node.temperature,
            max_tokens=node.max_tokens,
            contract=node.contract,
        )

        return result