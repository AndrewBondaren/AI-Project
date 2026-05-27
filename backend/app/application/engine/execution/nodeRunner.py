import logging
from datetime import datetime, timezone

from app.application.engine.dag.executionTrace import ExecutionTrace
from app.application.engine.nodes.nodeKind import NodeKind
from app.application.engine.nodes.nodeRegistry import NODE_REGISTRY
from app.application.engine.nodes.pojo.nodeResult import NodeResult
from app.application.engine.nodes.pojo.pythonNodeError import PythonNodeError
from app.application.engine.validation.nodeValidationContext import NodeValidationContext

logger = logging.getLogger(__name__)


class NodeRunner:

    def __init__(self, node_validator):
        self.node_validator = node_validator

    async def run(self, compiled_node, state, context) -> NodeResult | None:
        """
        Выполняет одну Python-ноду:
          - открывает трейс
          - вызывает executor из context["executors"]
          - валидирует результат через NodeValidator
          - пишет статус и результат в state
          - закрывает трейс

        Политика обработки ошибок:
          - PythonNodeError объявлена в node.possible_errors
              requires_replan=True  → статус "gated",  state.requires_replan выставляется
              requires_replan=False → статус "failed",  fail-fast в DAGExecutor
          - PythonNodeError НЕ объявлена → статус "failed" (баг в ноде)
          - любое другое исключение    → статус "failed" (инфраструктурная ошибка)
        """
        node = compiled_node.node
        state.node_status[node.id] = "running"
        state.execution_order.append(node.id)

        logger.info("node_start node_id=%s", node.id)

        trace = ExecutionTrace(
            node_id=node.id,
            start_time=datetime.now(timezone.utc),
            input=dict(state.node_results),
            output=None,
        )

        try:
            registration = NODE_REGISTRY.get(node.id)
            if registration.kind != NodeKind.PYTHON:
                raise TypeError(
                    f"Node '{node.id}' is LLM — executed via LLMAggregateExecutor, not NodeRunner"
                )
            executor = context["executors"][registration.executor_cls]

            node_result: NodeResult = await executor.execute(node, state, context)

            ctx = NodeValidationContext(
                node=node,
                output=node_result.data,
                state=state,
            )
            validation = self.node_validator.validate(ctx)

            if not validation.ok:
                state.node_status[node.id] = "failed"
                state.node_errors.setdefault(node.id, []).append({
                    "status": validation.status.value,
                    "errors": [e.code for e in validation.errors],
                })
                trace.status = "failed"
                trace.error = validation.reason
                logger.warning(
                    "node_validation_failed node_id=%s reason=%s errors=%s",
                    node.id,
                    validation.reason,
                    [e.code for e in validation.errors],
                )
                return None

            state.node_status[node.id] = "success"
            state.node_results[node.id] = node_result.data
            trace.output = node_result.data
            trace.status = "success"
            logger.info("node_success node_id=%s", node.id)

            return node_result

        except PythonNodeError as e:
            declared = node.possible_errors or []
            is_declared = any(isinstance(e, cls) for cls in declared)

            if not is_declared:
                # Ошибка не объявлена в possible_errors — баг в ноде
                state.node_status[node.id] = "failed"
                state.node_errors.setdefault(node.id, []).append({
                    "error": f"Undeclared PythonNodeError '{type(e).__name__}': {e}"
                })
                trace.status = "failed"
                trace.error = str(e)
                logger.error(
                    "node_undeclared_error node_id=%s error_type=%s msg=%s",
                    node.id, type(e).__name__, e,
                )
                return None

            if e.requires_replan:
                # Ожидаемый переход: gate-нода сигнализирует смену задачи
                if state.requires_replan:
                    # Две ноды одного уровня пытаются сделать replan — конфликт.
                    # В текущей архитектуре gate-ноды не должны быть в одном параллельном уровне.
                    raise RuntimeError(
                        f"Replan conflict: node '{node.id}' wants to transition to "
                        f"{e.next_task_type}, but state already has requires_replan=True "
                        f"with next_task_type={state.next_task_type}. "
                        f"Gate-nodes must not share a parallel level."
                    )
                state.requires_replan = True
                state.next_task_type = e.next_task_type
                state.replan_reason = e.replan_reason or str(e)
                if e.user_message:
                    state.user_error = e.user_message
                state.node_status[node.id] = "gated"
                trace.status = "gated"
                trace.error = e.code
                logger.info(
                    "node_gated node_id=%s code=%s next_task=%s reason=%s",
                    node.id, e.code, e.next_task_type, state.replan_reason,
                )
            else:
                # Объявленная фатальная ошибка (битые данные и т.п.)
                if e.user_message:
                    state.user_error = e.user_message
                state.node_status[node.id] = "failed"
                state.node_errors.setdefault(node.id, []).append({
                    "code": e.code,
                    "error": str(e),
                })
                trace.status = "failed"
                trace.error = str(e)
                logger.error(
                    "node_fatal_error node_id=%s code=%s error=%s",
                    node.id, e.code, e,
                )

            return None

        except Exception as e:
            state.node_status[node.id] = "failed"
            state.node_errors.setdefault(node.id, []).append({"error": str(e)})
            trace.status = "failed"
            trace.error = str(e)
            logger.exception("node_error node_id=%s", node.id)
            return None

        finally:
            trace.end_time = datetime.now(timezone.utc)
            state.traces.append(trace)
