# TODO(B2/B2-L15): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.execution.pythonNodeExecutor.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from app.application.engine.nodes.pojo.nodeResult import NodeResult


class PythonNodeExecutor:

    async def execute(self, node, state, context) -> NodeResult:
        return await node.execute(state, context)
