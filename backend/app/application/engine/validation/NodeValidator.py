from backend.app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus


class NodeValidator:

    def validate(self, node, output, state) -> ValidationResult:

        # -----------------------
        # CHAT example logic
        # -----------------------
        if node.id == "intent_detection":

            if not isinstance(output.get("task_list"), list):
                return ValidationResult(
                    status=ValidationStatus.RETRY,
                    reason="task_list must be list"
                )

            if len(output["task_list"]) == 0:
                return ValidationResult(
                    status=ValidationStatus.RETRY,
                    reason="empty intent"
                )

        # -----------------------
        # SCENE consistency example
        # -----------------------
        if node.id == "scene_generation":

            if "location" not in output:
                return ValidationResult(
                    status=ValidationStatus.RETRY,
                    reason="scene missing location"
                )

            if output.get("actors") and len(output["actors"]) > 10:
                return ValidationResult(
                    status=ValidationStatus.FAIL,
                    reason="too many actors (world rule violation)"
                )

        return ValidationResult(status=ValidationStatus.OK)