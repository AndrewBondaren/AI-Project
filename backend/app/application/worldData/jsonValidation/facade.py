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
    ValidationKind,
    ValidationRequest,
    ValidationResult,
)


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
