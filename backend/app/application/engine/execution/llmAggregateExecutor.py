import json

from app.application.engine.validation.validationStatus import ValidationStatus
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

        payload = self.payload_builder.build(nodes=nodes, dsl_keys=dsl_keys, state=state)
        messages = [
            {"role": "user", "content": json.dumps(payload.to_dict(), ensure_ascii=False)}
        ]

        raw = await client.chat(
            model=state.session.model,
            messages=messages,
        )

        # парсим JSON
        try:
            response = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLMAggregateExecutor: invalid JSON on first call: {e}")

        messages.append({"role": "assistant", "content": raw})

        # валидируем все секции
        failed, node_errors = self._validate_all(nodes, response, state)

        if failed:
            failed_nodes = [n for n in nodes if n.id in failed]

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