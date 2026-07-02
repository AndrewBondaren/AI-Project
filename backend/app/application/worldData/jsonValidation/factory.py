"""Default registry and orchestrator — JV-1 + JV-2."""

from __future__ import annotations

from app.application.worldData.jsonValidation.orchestrator import (
    N1SNormalizeStage,
    PrepareContextStage,
    RegistryIndexBuilderStage,
    RunValidatorsStage,
    ValidationOrchestrator,
)
from app.application.worldData.jsonValidation.registry import ValidatorRegistry
from app.application.worldData.jsonValidation.validators.connectionEdgeRow import ConnectionEdgeRowValidator
from app.application.worldData.jsonValidation.validators.connectionNodeRow import ConnectionNodeRowValidator
from app.application.worldData.jsonValidation.validators.declareTopology import DeclareTopologyValidator
from app.application.worldData.jsonValidation.validators.envelope import EnvelopeValidator
from app.application.worldData.jsonValidation.validators.namedLocationRow import NamedLocationRowValidator
from app.application.worldData.jsonValidation.validators.registryRefs import RegistryRefsValidator
from app.application.worldData.jsonValidation.validators.worldRow import WorldRowValidator


def build_default_registry() -> ValidatorRegistry:
    registry = ValidatorRegistry()
    registry.register(EnvelopeValidator())
    registry.register(WorldRowValidator())
    registry.register(RegistryRefsValidator())
    registry.register(NamedLocationRowValidator())
    registry.register(ConnectionNodeRowValidator())
    registry.register(ConnectionEdgeRowValidator())
    registry.register(DeclareTopologyValidator())
    return registry


def build_default_orchestrator() -> ValidationOrchestrator:
    return ValidationOrchestrator([
        PrepareContextStage(),
        N1SNormalizeStage(),
        RegistryIndexBuilderStage(),
        RunValidatorsStage(),
    ])
