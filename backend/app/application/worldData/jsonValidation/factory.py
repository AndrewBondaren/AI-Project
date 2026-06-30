"""Default registry and orchestrator — JV-1 + JV-2 + JV-3 + JV-4 + JV-5."""

from __future__ import annotations

from app.application.worldData.jsonValidation.orchestrator import (
    HydrologyClimateNormalizeStage,
    N1SNormalizeStage,
    PrepareContextStage,
    RegistryIndexBuilderStage,
    RunValidatorsStage,
    SeedIndexBuilderStage,
    ValidationOrchestrator,
)
from app.application.worldData.jsonValidation.registry import ValidatorRegistry
from app.application.worldData.jsonValidation.validators.climatePolicy import ClimatePolicyValidator
from app.application.worldData.jsonValidation.validators.connectionEdgeRow import ConnectionEdgeRowValidator
from app.application.worldData.jsonValidation.validators.connectionNodeRow import ConnectionNodeRowValidator
from app.application.worldData.jsonValidation.validators.declareTopology import DeclareTopologyValidator
from app.application.worldData.jsonValidation.validators.envelope import EnvelopeValidator
from app.application.worldData.jsonValidation.validators.hydrologyPolicy import HydrologyPolicyValidator
from app.application.worldData.jsonValidation.validators.namedLocationRow import NamedLocationRowValidator
from app.application.worldData.jsonValidation.validators.raceContract import RaceContractValidator
from app.application.worldData.jsonValidation.validators.raceRow import RaceRowValidator
from app.application.worldData.jsonValidation.validators.registryRefs import RegistryRefsValidator
from app.application.worldData.jsonValidation.validators.seedTable import SeedTableValidator
from app.application.worldData.jsonValidation.validators.worldRow import WorldRowValidator
from app.application.worldData.jsonValidation.validators.worldTemplateRegistries import (
    WorldTemplateRegistriesValidator,
)


def build_default_registry() -> ValidatorRegistry:
    registry = ValidatorRegistry()
    registry.register(EnvelopeValidator())
    registry.register(WorldRowValidator())
    registry.register(HydrologyPolicyValidator())
    registry.register(ClimatePolicyValidator())
    registry.register(RegistryRefsValidator())
    registry.register(WorldTemplateRegistriesValidator())
    registry.register(NamedLocationRowValidator())
    registry.register(ConnectionNodeRowValidator())
    registry.register(ConnectionEdgeRowValidator())
    registry.register(DeclareTopologyValidator())
    registry.register(RaceRowValidator())
    registry.register(RaceContractValidator())
    registry.register(SeedTableValidator())
    return registry


def build_default_orchestrator() -> ValidationOrchestrator:
    return ValidationOrchestrator([
        PrepareContextStage(),
        N1SNormalizeStage(),
        HydrologyClimateNormalizeStage(),
        RegistryIndexBuilderStage(),
        SeedIndexBuilderStage(),
        RunValidatorsStage(),
    ])
