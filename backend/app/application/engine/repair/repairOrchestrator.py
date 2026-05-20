import json
import logging

from app.application.llm.models import ChatMessage
from app.application.engine.prompt.schemaBuilder import build_strict_schema
from app.application.events.eventBus import emit
from app.application.events.sseEvents import NodeStatusEvent, NodePhase, ThinkingEvent

logger = logging.getLogger(__name__)
from app.application.engine.errors import UserInputError
from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.repair.repairBuilder import RepairBuilder
from app.application.engine.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.validation.nodeValidationError import NodeValidationError, NodeErrorSeverity
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus


class RepairOrchestrator:
    """
    Владеет repair loop для LLM-нод внутри одной conversation.

    Ответственность:
      - подобрать DSL-патчи по типам ошибок
      - делегировать построение payload в RepairBuilder
      - отправить repair вызов в той же conversation
      - валидировать ответ
      - повторять до repair_iterations
      - если исчерпали — бросить RuntimeError
    """

    def __init__(self, dsl_resolver: DSLResolver, repair_builder: RepairBuilder, llm_validator):
        self.dsl_resolver = dsl_resolver
        self.repair_builder = repair_builder
        self.llm_validator = llm_validator

    async def repair(
        self,
        failed_nodes: list,
        all_nodes: list,
        dsl_keys: dict,
        messages: list,
        client,
        state,
        enable_thinking: bool = False,
    ) -> dict:
        """
        Чинит failed_nodes внутри текущей conversation (messages).
        Возвращает dict {node_id: output} для всех успешно починенных нод.
        Бросает RuntimeError если repair_iterations исчерпаны.
        """

        max_attempts = state.session.repair_iterations
        attempt = 0
        current_failed = {node.id: node for node in failed_nodes}

        logger.warning(
            "repair_start nodes=%s max_attempts=%d",
            list(current_failed.keys()),
            max_attempts,
        )

        while attempt < max_attempts:

            task_type = state.task_type.value
            for node in current_failed.values():
                await emit(NodeStatusEvent(node_id=node.id, task_type=task_type, phase=NodePhase.REPAIRING))

            # расширяем dsl_keys патчами для текущих failed нод
            for node in current_failed.values():
                last_validation = self._get_last_validation(node.id, state)
                if last_validation:
                    patch_keys = self.dsl_resolver.resolve_patches(node, last_validation)
                    dsl_keys[node.id] = self.dsl_resolver.update(dsl_keys[node.id], patch_keys)

            # делегируем построение payload в RepairBuilder
            repair_payload = self.repair_builder.build(
                failed_nodes=list(current_failed.values()),
                dsl_keys=dsl_keys,
                state=state,
            )

            messages.append(ChatMessage(
                role="user",
                content=json.dumps(repair_payload.to_dict(), ensure_ascii=False, separators=(",", ":")),
            ))

            node_id = ",".join(current_failed.keys())
            await emit(ThinkingEvent(node_id=node_id, text="", elapsed_ms=0))

            raw = await client.chat(
                model=state.session.model,
                messages=messages,
                response_format_schema=repair_payload.response_format_schema,
                enable_thinking=enable_thinking,
                node_id=node_id,
            )

            messages.append(
                ChatMessage(role="assistant", content=raw if isinstance(raw, str) else json.dumps(raw, separators=(",", ":")))
            )

            # парсим ответ
            try:
                response = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                attempt += 1
                continue

            # валидируем только current_failed ноды
            still_failed, validation_errors = self._validate_failed(
                nodes=list(current_failed.values()),
                response=response,
                state=state,
                repair_attempt=attempt,
            )

            # сохраняем ошибки для следующей итерации
            for node_id, error_info in validation_errors.items():
                state.node_errors.setdefault(node_id, []).append({
                    "repair_attempt": attempt,
                    "errors": [e.code for e in error_info["validation"].errors],
                })

            if not still_failed:
                logger.info(
                    "repair_success nodes=%s attempt=%d",
                    list(current_failed.keys()),
                    attempt,
                )
                return {
                    node_id: response[node_id]
                    for node_id in current_failed
                    if node_id in response
                }

            logger.warning(
                "repair_attempt_failed attempt=%d still_failed=%s",
                attempt,
                still_failed,
            )
            current_failed = {
                node_id: node
                for node_id, node in current_failed.items()
                if node_id in still_failed
            }
            attempt += 1

        logger.error(
            "repair_limit_exceeded nodes=%s max_attempts=%d",
            list(current_failed.keys()),
            max_attempts,
        )
        raise RuntimeError(
            f"RepairOrchestrator: repair_limit_exceeded after {max_attempts} attempts. "
            f"Failed nodes: {list(current_failed.keys())}"
        )

    # --------------------------------------------------
    # VALIDATE
    # --------------------------------------------------

    def _validate_failed(
        self,
        nodes: list,
        response: dict,
        state,
        repair_attempt: int,
    ) -> tuple[list[str], dict]:

        failed = []
        errors = {}

        for node in nodes:
            node_id = node.id

            if node_id not in response:
                failed.append(node_id)
                errors[node_id] = {
                    "validation": ValidationResult(
                        status=ValidationStatus.RETRY,
                        errors=[NodeValidationError(
                            code="missing_section",
                            message=f"missing section '{node_id}' in repair response",
                            severity=NodeErrorSeverity.RETRY,
                        )],
                    ),
                }
                continue

            ctx = NodeValidationContext(
                node=node,
                output=response[node_id],
                state=state,
                repair_attempt=repair_attempt,
            )

            validation = self.llm_validator.validate(ctx)

            if validation.status == ValidationStatus.USER_ERROR:
                raise UserInputError(validation.errors[0].message)

            if not validation.ok:
                failed.append(node_id)
                errors[node_id] = {"validation": validation}

        return failed, errors

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------

    def _get_last_validation(self, node_id: str, state) -> ValidationResult | None:
        """Восстанавливает ValidationResult из state.node_errors для подбора DSL-патчей."""
        errors = state.node_errors.get(node_id)
        if not errors:
            return None

        codes = errors[-1].get("errors", [])
        if not codes:
            return None

        return ValidationResult(
            status=ValidationStatus.RETRY,
            errors=[
                NodeValidationError(
                    code=code,
                    message=code,
                    severity=NodeErrorSeverity.RETRY,
                )
                for code in codes
            ],
        )