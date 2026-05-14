import inspect


class PythonNodeExecutor:

    async def execute(self, node, state, context):
        handler = node.handler

        if handler is None:
            raise ValueError(f"PythonNode {node.id} has no handler")

        if inspect.iscoroutinefunction(handler):
            return await handler(state, context)

        # sync handler
        return handler(state)