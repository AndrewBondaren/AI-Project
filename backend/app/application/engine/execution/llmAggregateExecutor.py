import json

from app.application.engine.validation.validationStatus import ValidationStatus
from app.application.engine.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.validation.nodeValidationError import NodeValidationError, NodeErrorSeverity
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus

class LLMAggregateExecutor:
    """
    Выполняет одну LLM temperature-группу как единый агрегированный вызов.

    Порядок:
      1. LLMGroupPayloadBuilder собирает запрос из всех нод группы
      2. Один client.chat() на группу
      3. LLMValidator валидирует каждую секцию:
           - ContractValidator — структура (contract_json)
           - NodeValidator     — бизнес-логика (node.validator)
      4. При ошибках — repair loop внутри той же conversation:
           - DSLResolver подбирает dsl_patch по типу ошибки
           - LLMGroupPayloadBuilder пересобирает payload с расширенным DSL
      5. Все секции прошли → накапливаем в state.pending_patches
         (PatchApplier применит атомарно в конце всех passes)
      6. Исчерпали repair_iterations → бросаем исключение
    """

    def __init__(self, payload_builder, llm_validator, dsl_resolver, dsl_registry, router):
        self.payload_builder = payload_builder
        self.llm_validator = llm_validator
        self.dsl_resolver = dsl_resolver
        self.dsl_registry = dsl_registry
        self.router = router

    async def execute(self, llm_group, plan, state, context):

        node_ids = [nid for level in llm_group.levels for nid in level]
        nodes = [plan.nodes[nid].node for nid in node_ids]

        client = self.router.get(state.session.llm_provider)

        # dsl_keys на старте — базовые DSL каждой ноды
        dsl_keys = {node.id: [node.dsl] for node in nodes}

        payload = self._build_payload(nodes, dsl_keys, state)
        messages = [
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ]

        max_attempts = state.session.repair_iterations
        attempt = 0

        while attempt <= max_attempts:

            raw = await client.chat(
                model=state.session.model,
                messages=messages,
            )

            # парсим JSON
            try:
                response = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError as e:
                messages.append({"role": "assistant", "content": str(raw)})
                messages.append(self._json_error_msg(str(e)))
                attempt += 1
                continue

            # валидируем все секции
            failed, node_errors = self._validate_all(nodes, response, state, repair_attempt=attempt)

            if not failed:
                # все секции прошли — накапливаем патчи
                for node in nodes:
                    state.pending_patches.append({
                        "node_id": node.id,
                        "output": response[node.id],
                    })
                    state.node_status[node.id] = "success"
                return

            # расширяем dsl_keys патчами для упавших нод
            for node in nodes:
                if node.id in node_errors:
                    validation = node_errors[node.id]["validation"]
                    patch_key = self.dsl_resolver.resolve_patch(node, validation)
                    dsl_keys[node.id] = self.dsl_resolver.update(dsl_keys[node.id], patch_key)

            # пересобираем payload с расширенным DSL только для failed нод
            repair_payload = self._build_repair_payload(
                nodes=nodes,
                dsl_keys=dsl_keys,
                failed_ids=list(node_errors.keys()),
                errors={nid: v["reason"] for nid, v in node_errors.items()},
                state=state,
            )

            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": json.dumps(repair_payload, ensure_ascii=False),
            })
            attempt += 1

        # исчерпали попытки — бросаем исключение, DAGExecutor остановит пайплайн
        failed_ids = [
            node.id for node in nodes
            if node.id not in {p["node_id"] for p in state.pending_patches}
        ]
        raise RuntimeError(
            f"LLMAggregateExecutor: repair_limit_exceeded after {max_attempts} attempts. "
            f"Failed nodes: {failed_ids}"
        )

    # --------------------------------------------------
    # BUILD
    # --------------------------------------------------

    def _build_payload(self, nodes, dsl_keys: dict, state) -> dict:
        """Первый вызов — базовый DSL каждой ноды."""
        payload = {
            "player_message": state.message,
            "language": "RU", #Вынести в настройку и принимать из frontEnd
            "contract_json": self._build_contracts(nodes),
        }
        for node in nodes:
            payload[node.id] = {
                "dsl": self._resolve_dsl(dsl_keys[node.id]),
                "context_data": self._collect_deps(node, state),
            }
        return payload

    def _build_repair_payload(self, nodes, dsl_keys, failed_ids, errors, state) -> dict:
        """Repair вызов — только failed ноды с расширенным DSL и описанием ошибок."""
        payload = {
            "player_message": state.message,
            "language": "RU", #Вынести в настройку и принимать из frontEnd
            "type": "repair",
            "contract_json": self._build_contracts(
                [n for n in nodes if n.id in failed_ids]
            ),
            "errors": {
                nid: [e.code for e in v["validation"].errors]
                for nid, v in errors.items()
            },
        }
        for node in nodes:
            if node.id in failed_ids:
                payload[node.id] = {
                    "dsl": self._resolve_dsl(dsl_keys[node.id]),
                    "context_data": self._collect_deps(node, state),
                }
        return payload

    def _resolve_dsl(self, keys: list[str]) -> str:
        """Читает и склеивает DSL-файлы по ключам."""
        parts = [self.dsl_registry.get(key) for key in keys]
        return "\n\n".join(parts)

    def _build_contracts(self, nodes) -> dict:
        return {
            node.id: node.contract_json.model_json_schema()
            for node in nodes
            if node.contract_json is not None
        }

    def _collect_deps(self, node, state) -> dict:
        return {
            dep: state.node_results.get(dep)
            for dep in node.deps
            if dep in state.node_results
        }

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
                errors[node_id] = {
                    "validation": validation,
                    "reason": validation.reason,
                }

        return failed, errors

    # --------------------------------------------------
    # MESSAGES
    # --------------------------------------------------

    def _json_error_msg(self, error: str) -> dict:
        return {
            "role": "user",
            "content": json.dumps({
                "type": "repair",
                "error": f"JSON parse error: {error}",
                "hint": "Return a single valid JSON object with keys matching node ids",
            }, ensure_ascii=False),
        }