import inspect

from app.application.engine.nodes.pojo.nodeResult import NodeResult


class PythonNodeExecutor:

    async def execute(self, node, state, context) -> NodeResult:

        handler = node.handler

        if handler is None:
            raise ValueError(f"PythonNode '{node.id}' has no handler")

        if inspect.iscoroutinefunction(handler):
            data = await handler(state, context)
        else:
            data = handler(state)

        # handler декларирует requires_replan через NodeResult напрямую,
        # или возвращает голые данные — оборачиваем
        if isinstance(data, NodeResult):
            return data

        return NodeResult(data=data)