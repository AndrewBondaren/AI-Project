"""ValidationOrchestrator — linear write-path steps — docs/tz_json_validation.md § Orchestrator."""

from __future__ import annotations

from typing import Protocol

from app.application.worldData.jsonValidation.registry import ValidatorRegistry
from app.application.worldData.jsonValidation.types import (
    SectionKey,
    ValidationContext,
    ValidationKind,
    active_section_keys,
)


class OrchestratorStep(Protocol):
    def run(self, ctx: ValidationContext, registry: ValidatorRegistry) -> None: ...


class ValidationOrchestrator:
    """Linear coordinator: prepare → normalize → index → validators (not engine DAG)."""

    def __init__(self, steps: list[OrchestratorStep] | None = None) -> None:
        self._steps: list[OrchestratorStep] = list(steps or [])

    def run(self, ctx: ValidationContext, registry: ValidatorRegistry) -> None:
        for step in self._steps:
            step.run(ctx, registry)


class PrepareContextStage:
    """Step 1: resolve bundle shape and active sections from normalized payload."""

    def run(self, ctx: ValidationContext, registry: ValidatorRegistry) -> None:
        del registry
        req = ctx.request
        if req.kind == ValidationKind.BUNDLE:
            if not isinstance(ctx.normalized, dict):
                return
            ctx.bundle = ctx.normalized
            ctx.active_sections = active_section_keys(ctx.normalized)
            world = ctx.normalized.get("world")
            if isinstance(world, dict):
                uid = world.get("world_uid")
                if isinstance(uid, str):
                    ctx.world_uid = uid
            if req.world_uid:
                ctx.world_uid = req.world_uid
        elif req.kind == ValidationKind.SEED:
            pass
        elif req.kind == ValidationKind.SECTION:
            if not isinstance(ctx.normalized, dict):
                return
            ctx.bundle = ctx.normalized
            ctx.active_sections = active_section_keys(ctx.normalized) | frozenset({SectionKey.WORLD})
            if req.section is not None:
                ctx.active_sections |= frozenset({req.section})
            world = ctx.normalized.get("world")
            if isinstance(world, dict):
                uid = world.get("world_uid")
                if isinstance(uid, str):
                    ctx.world_uid = uid
            if req.world_uid:
                ctx.world_uid = req.world_uid
        elif req.kind == ValidationKind.CRUD_PATCH:
            pass


class N1SNormalizeStage:
    """Step 2: N1-S map → array on world blob (JV-1)."""

    def run(self, ctx: ValidationContext, registry: ValidatorRegistry) -> None:
        del registry
        if ctx.request.kind not in (ValidationKind.BUNDLE, ValidationKind.SECTION):
            return
        if ctx.has_errors:
            return
        bundle = ctx.normalized
        if not isinstance(bundle, dict):
            return
        world = bundle.get("world")
        if not isinstance(world, dict):
            return
        from app.application.worldData.jsonValidation.normalize.n1sSchemas import (
            normalize_world_n1s,
        )
        ctx.issues.extend(normalize_world_n1s(world))


class RegistryIndexBuilderStage:
    """Step 3: Pass 1 WorldRegistryIndex (JV-2)."""

    def run(self, ctx: ValidationContext, registry: ValidatorRegistry) -> None:
        del registry
        if ctx.has_errors:
            return
        bundle = ctx.normalized if isinstance(ctx.normalized, dict) else ctx.bundle
        if not isinstance(bundle, dict):
            return
        world = bundle.get("world")
        if not isinstance(world, dict):
            return
        from app.application.worldData.jsonValidation.index.worldRegistryIndex import (
            build_world_registry_index,
        )
        ctx.index = build_world_registry_index(world)


class RunValidatorsStage:
    """Step 4: invoke registered SchemaValidators."""

    def run(self, ctx: ValidationContext, registry: ValidatorRegistry) -> None:
        if ctx.request.kind == ValidationKind.SEED:
            sections: frozenset[SectionKey] = frozenset()
        elif isinstance(ctx.normalized, dict) and ctx.request.kind == ValidationKind.BUNDLE:
            sections = ctx.active_sections
        elif isinstance(ctx.normalized, dict) and ctx.request.kind == ValidationKind.SECTION:
            sections = ctx.active_sections
            if ctx.request.section is not None:
                sections = sections | frozenset({ctx.request.section})
            sections = sections | frozenset({SectionKey.WORLD})
        else:
            return
        for validator in registry.for_sections(sections):
            validator.validate(ctx)
