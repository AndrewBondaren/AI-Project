import asyncio

class PythonNodeExecutor:
    async def execute(self, node, state):
        if asyncio.iscoroutinefunction(node.handler):
            return await node.handler(state)
        return node.handler(state)