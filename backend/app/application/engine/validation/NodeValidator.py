from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus


class NodeValidator:

    def __init__(self, validator, repair_orchestrator):
        self.validator = validator
        self.repair = repair_orchestrator

    async def validate_with_repair(self, node, result, state):
        """
        Валидирует результат ноды. При WARN — запускает repair loop.
        Возвращает (result, ok: bool).
        """
        validation = self.validator.validate(node=node, output=result, state=state)

        if validation.ok:
            return result, True

        result, validation = await self._retry_until_valid(node, result, validation, state)

        if not validation.ok:
            self._record_failure(node.id, validation, state)
            return result, False

        return result, True

    # --------------------------------------------------

    async def _retry_until_valid(self, node, output, validation, state):

        if not node.retry_policy or not node.retry_policy.get("enabled"):
            return output, validation

        max_attempts = state.session.repair_iterations
        attempt = 0

        while not validation.ok:

            if validation.failed:
                return output, validation

            if attempt >= max_attempts:
                return output, ValidationResult(
                    status=ValidationStatus.FAIL,
                    reason=f"repair_limit_exceeded: {max_attempts}",
                )

            repaired = await self.repair.repair_node(
                node=node,
                output=output,
                reason=validation.reason,
                state=state,
            )
            attempt += 1

            if repaired is None:
                return output, validation

            output = repaired
            validation = self.validator.validate(node=node, output=output, state=state)

        return output, validation

    def _record_failure(self, node_id, validation, state):
        state.node_errors.setdefault(node_id, []).append({
            "status": validation.status.value,
            "error": validation.reason,
        })