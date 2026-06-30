"""JsonValidationFacade — entry point for master JSON validation."""

from __future__ import annotations

from copy import deepcopy

from app.application.worldData.jsonValidation.factory import (
    build_default_orchestrator,
    build_default_registry,
)
from app.application.worldData.jsonValidation.orchestrator import ValidationOrchestrator
from app.application.worldData.jsonValidation.registry import ValidatorRegistry
from app.application.worldData.jsonValidation.types import (
    ValidationContext,
    ValidationIssue,
    ValidationKind,
    ValidationRequest,
    ValidationResult,
)
from app.application.worldData.jsonValidation.validators.templates.barrierTemplate import (
    collect_barrier_template_issues,
)
from app.application.worldData.jsonValidation.validators.templates.buildingTemplate import (
    collect_building_template_issues,
)
from app.application.worldData.jsonValidation.validators.templates.districtTemplate import (
    collect_district_template_issues,
)

_TEMPLATE_COLLECTORS = {
    ValidationKind.BUILDING_TEMPLATE: collect_building_template_issues,
    ValidationKind.DISTRICT_TEMPLATE: collect_district_template_issues,
    ValidationKind.BARRIER_TEMPLATE: collect_barrier_template_issues,
}


class JsonValidationFacade:
    def __init__(
        self,
        registry: ValidatorRegistry | None = None,
        orchestrator: ValidationOrchestrator | None = None,
    ) -> None:
        self._registry = registry or build_default_registry()
        self._orchestrator = orchestrator or build_default_orchestrator()

    @property
    def registry(self) -> ValidatorRegistry:
        return self._registry

    @property
    def orchestrator(self) -> ValidationOrchestrator:
        return self._orchestrator

    async def validate(self, request: ValidationRequest) -> ValidationResult:
        if request.kind == ValidationKind.CHARACTER:
            return ValidationResult(ok=True)

        collector = _TEMPLATE_COLLECTORS.get(request.kind)
        if collector is not None:
            if not isinstance(request.payload, dict):
                return ValidationResult(
                    ok=False,
                    issues=[ValidationIssue(
                        schema_id="SCH-ENVELOPE",
                        path="$",
                        code="INVALID_TYPE",
                        message="template payload must be an object",
                        severity="error",
                    )],
                )
            issues = collector(request.payload)
            has_errors = any(i.severity == "error" for i in issues)
            return ValidationResult(
                ok=not has_errors,
                issues=issues,
                normalized=deepcopy(request.payload),
            )

        ctx = ValidationContext(request=request)
        if isinstance(request.payload, dict):
            ctx.normalized = deepcopy(request.payload)
        elif isinstance(request.payload, list):
            ctx.normalized = deepcopy(request.payload)

        self._orchestrator.run(ctx, self._registry)

        return ValidationResult(
            ok=not ctx.has_errors,
            issues=list(ctx.issues),
            normalized=ctx.normalized,
        )
