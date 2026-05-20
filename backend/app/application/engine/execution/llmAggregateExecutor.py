import json
import logging
import time

from app.application.llm.models import ChatMessage
from app.application.engine.validation.validationStatus import ValidationStatus
from app.application.events.eventBus import emit
from app.application.events.sseEvents import ThinkingEvent

logger = logging.getLogger(__name__)
from app.application.engine.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.validation.nodeValidationError import NodeValidationError, NodeErrorSeverity
from app.application.engine.validation.validationStatus import ValidationResult


class LLMAggregateExecutor:
    """
    Выполняет одну LLM temperature-группу как единый агрегированный вызов.

    Ответственность:
      - собрать payload группы
      - отправить один client.chat()
      - валидировать ответ
      - при ошибках — делегировать в RepairOrchestrator
      - успешные результаты накопить в state.pending_patches
    """

    def __init__(self, payload_builder, llm_validator, dsl_resolver, dsl_registry, repair_orchestrator, router):
        self.payload_builder = payload_builder
        self.llm_validator = llm_validator
        self.dsl_resolver = dsl_resolver
        self.dsl_registry = dsl_registry
        self.repair_orchestrator = repair_orchestrator
        self.router = router

    async def execute(self, llm_group, plan, state, context):

        node_ids = [nid for level in llm_group.levels for nid in level]
        nodes = [plan.nodes[nid].node for nid in node_ids]

        client = self.router.get(state.session.llm_provider)

        dsl_keys = {node.id: [node.dsl] for node in nodes}
        enable_thinking = any(node.enable_thinking for node in nodes)

        payload = self.payload_builder.build(nodes=nodes, dsl_keys=dsl_keys, state=state)
        # NOTE: весь payload идёт в role="user". Альтернатива — role="system" для global_dsl,
        # role="user" только для player_message + sections. Некоторые модели точнее следуют
        # инструкциям в system роли — стоит проверить если intent detection будет давать сбои.
        messages = [
            ChatMessage(
                role="user",
                content=json.dumps(payload.to_dict(), ensure_ascii=False, separators=(",", ":")),
            )
        ]

        logger.info(
            "llm_call_start provider=%s model=%s nodes=%s",
            state.session.llm_provider,
            state.session.model,
            [n.id for n in nodes],
        )

        # signal frontend that LLM call is starting
        _primary_node_id = node_ids[0] if len(node_ids) == 1 else ",".join(node_ids)
        await emit(ThinkingEvent(node_id=_primary_node_id, text="", elapsed_ms=0))

        _t0 = time.perf_counter()
        raw = await client.chat(
            model=state.session.model,
            messages=messages,
            response_format_schema=payload.response_format_schema,
            enable_thinking=enable_thinking,
            node_id=node_ids[0] if len(node_ids) == 1 else ",".join(node_ids),
        )
        logger.info(
            "llm_call_end provider=%s model=%s elapsed_ms=%d",
            state.session.llm_provider,
            state.session.model,
            round((time.perf_counter() - _t0) * 1000),
        )

        # парсим JSON
        try:
            response = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLMAggregateExecutor: invalid JSON on first call: {e}")

        messages.append(ChatMessage(role="assistant", content=raw if isinstance(raw, str) else json.dumps(raw, separators=(",", ":"))))

        # валидируем все секции
        failed, node_errors = self._validate_all(nodes, response, state)

        if failed:
            failed_nodes = [n for n in nodes if n.id in failed]

            logger.warning("llm_validation_failed nodes=%s", failed)

            # сохраняем ошибки первого вызова
            for node_id, error_info in node_errors.items():
                state.node_errors.setdefault(node_id, []).append({
                    "repair_attempt": 0,
                    "errors": [e.code for e in error_info["validation"].errors],
                })

            # делегируем repair — он работает внутри той же conversation
            repaired = await self.repair_orchestrator.repair(
                failed_nodes=failed_nodes,
                all_nodes=nodes,
                dsl_keys=dsl_keys,
                messages=messages,
                client=client,
                state=state,
                enable_thinking=enable_thinking,
            )

            # мержим repaired с успешными из первого вызова
#            for node in nodes:
#                if node.id not in failed:
#                    response[node.id] = response[node.id]
#                else:
#                    response[node.id] = repaired[node.id]

            for node_id, output in repaired.items():
                response[node_id] = output

        # все секции ok — накапливаем патчи
        for node in nodes:
            output = response[node.id]
            state.node_results[node.id] = output
            state.pending_patches.append({
                "node_id": node.id,
                "output": response[node.id],
            })
            state.node_status[node.id] = "success"

    # --------------------------------------------------
    # VALIDATE
    # --------------------------------------------------

    def _validate_all(self, nodes, response, state, repair_attempt: int = 0) -> tuple[list, dict]:

        failed = []
        errors = {}

        for node in nodes:
            node_id = node.id

            if node_id not in response:
                errors[node_id] = {
                    "validation": ValidationResult(
                        status=ValidationStatus.RETRY,
                        errors=[NodeValidationError(
                            code="missing_section",
                            message=f"missing section '{node_id}' in response",
                            severity=NodeErrorSeverity.RETRY,
                        )],
                    ),
                }
                failed.append(node_id)
                continue

            ctx = NodeValidationContext(
                node=node,
                output=response[node_id],
                state=state,
                repair_attempt=repair_attempt,
            )

            validation = self.llm_validator.validate(ctx)

            if not validation.ok:
                failed.append(node_id)
                errors[node_id] = {"validation": validation}

        return failed, errors