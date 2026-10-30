"""Water admission declarations and captured observations; the common engine decides."""

from enum import StrEnum
from typing import Annotated, Generic, Self
from typing_extensions import TypeVar

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.placement.placementFields import WaterCategoryPlacementFields, WaterSourcePlacementFields
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSource
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.policy.declarations.fieldPolicy import EnabledFor, SelectByValue, ValueCase
from app.dataModel.policy.declarations.policyCases import PolicyCaseDeclaration
from app.dataModel.policy.declarations.policyDeclaration import AdmissionPolicy, PolicyOwner
from app.dataModel.policy.objectAdmissionPolicyDefinition import PlacementPolicyDefaults
from app.dataModel.policy.policyBindings import PolicySupportFact
from app.dataModel.policy.policyEnums import PolicyDisableReason, PolicyStage
from app.dataModel.policy.policyFacts import FactValue
from app.dataModel.policy.policyReferences import DirectValueRef, FactValueRef, PriorityValueRef
from app.dataModel.policy.policyRules import DisableEffect, Equal
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind
from app.dataModel.validation.immutableValue import validate_immutable


type WaterPlacementPolicySource = WaterDesignSource | DeclaredCoastline


H = TypeVar("H", bound=HydrologyPlan, default=HydrologyPlan)


class HydrologyPolicySnapshot(BaseModel, Generic[H], frozen=True):
    """Caller-captured evidence, bound to one hydrology revision; no live lookup."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    world_uid: EntityUid
    supports: tuple[PolicySupportFact, ...]
    hydrology: PlanEnvelope[H] | None
    source_mapping: SourceBodyMapping | None
    mapping_hydrology_ref: PlanRef | None

    @model_validator(mode="after")
    def coherent_evidence(self) -> Self:
        validate_immutable(self)
        if len({support.uid for support in self.supports}) != len(self.supports):
            raise ValueError("duplicate support observations")
        if self.hydrology is not None and self.hydrology.ref.key.world_uid != self.world_uid:
            raise ValueError("hydrology snapshot world mismatch")
        if (self.source_mapping is None) != (self.mapping_hydrology_ref is None):
            raise ValueError("mapping and its hydrology reference must be supplied together")
        if self.mapping_hydrology_ref is not None:
            if self.hydrology is None or self.mapping_hydrology_ref != self.hydrology.ref:
                raise ValueError("source mapping must bind to the supplied hydrology revision")
        return self


class HydrologyPolicyFacts(BaseModel, frozen=True):
    """Observed purpose/category and water presence, never an admission decision."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    purpose: CoastlinePurpose
    category: WaterGenerationCategory
    target_has_water: FactValue[bool | None]


class HydrologyPlacementPolicy(PolicyOwner):
    """Nominal placement owner, separate from generation mode selection."""


class HydrologyPlacementCase(StrEnum):
    TARGET_SUPPORT = "target_support"
    DRY_BOUNDARY = "dry_boundary"
    PROCEDURAL_DISABLED = "procedural_disabled"
    PROCEDURAL_DECLARED_ONLY = "procedural_declared_only"


class HydrologyProceduralGenerationInputs(BaseModel, frozen=True):
    """Computed generation behavior for native procedural source admission."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    execution_mode: HydrologyExecutionMode


PROCEDURAL_GENERATION_CASES = (
    PolicyCaseDeclaration(key=HydrologyPlacementCase.PROCEDURAL_DISABLED,
        conditions=(Equal(DirectValueRef(FieldRef(lambda: HydrologyProceduralGenerationInputs,
            lambda inputs: inputs.execution_mode)), HydrologyExecutionMode.DISABLED),),
        effect=DisableEffect(PolicyDisableReason.ENABLED_FALSE), stage=PolicyStage.ABSOLUTE_GATE),
    PolicyCaseDeclaration(key=HydrologyPlacementCase.PROCEDURAL_DECLARED_ONLY,
        conditions=(Equal(DirectValueRef(FieldRef(lambda: HydrologyProceduralGenerationInputs,
            lambda inputs: inputs.execution_mode)), HydrologyExecutionMode.DECLARED_ONLY),),
        effect=DisableEffect(PolicyDisableReason.DOMAIN_RULE), reason=WaterPolicyReason.DECLARED_ONLY,
        stage=PolicyStage.ABSOLUTE_GATE),
)


BOUNDARY_PURPOSE = Equal(DirectValueRef(FieldRef(
    lambda: HydrologyPolicyFacts, lambda facts: facts.purpose)), CoastlinePurpose.BODY_BOUNDARY)

HYDROLOGY_PLACEMENT_POLICY = AdmissionPolicy[DesignedWaterStrategyKind, WaterPolicyReason](
    owner=HydrologyPlacementPolicy,
    behavior_type=DesignedWaterStrategyKind,
    reason_type=WaterPolicyReason,
    authored_priority_ref=PriorityValueRef(FieldRef(
        lambda: WaterSourcePlacementFields, lambda source: source.placement_specificity)),
    domain_priority_ref=PriorityValueRef(FieldRef(
        lambda: WaterCategoryPlacementFields, lambda category: category.placement_specificity)),
    terminal_priority_ref=PriorityValueRef(FieldRef(
        lambda: PlacementPolicyDefaults, lambda defaults: defaults.placement_specificity)),
    cases=(PolicyCaseDeclaration(
        key=HydrologyPlacementCase.DRY_BOUNDARY,
        conditions=(BOUNDARY_PURPOSE, Equal(FactValueRef(FieldRef(
            lambda: HydrologyPolicyFacts, lambda facts: facts.target_has_water)), False)),
        effect=DisableEffect(PolicyDisableReason.DOMAIN_RULE),
        reason=WaterPolicyReason.DRY_TARGET,
        stage=PolicyStage.SUPPORT),))


class HydrologyPlacementGateInputs(BaseModel, frozen=True):
    """Required captured booleans; no settings defaults or gate execution here."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    world_enabled: Annotated[StrictBool, EnabledFor(HYDROLOGY_PLACEMENT_POLICY)]
    category_enabled: Annotated[StrictBool, EnabledFor(HYDROLOGY_PLACEMENT_POLICY)]


class HydrologyPlacementBehaviorInputs(BaseModel, frozen=True):
    """Already resolved strategy; common SelectByValue selects the behavior."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    strategy: Annotated[DesignedWaterStrategyKind, SelectByValue(HYDROLOGY_PLACEMENT_POLICY, tuple(
        ValueCase(when=strategy, behavior=strategy) for strategy in DesignedWaterStrategyKind))]
