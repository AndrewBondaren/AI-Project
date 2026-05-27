from app.application.engine.nodes.pojo.nodeResult import NodeResult


class PythonNodeExecutor:

    async def execute(self, node, state, context) -> NodeResult:
        return await node.execute(state, context)
